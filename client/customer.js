/**
 * Chess Client - Lobby, room browser, game board, chat, and move history.
 */

const state = {
    playerId: `player-${Date.now()}`,
    roomId: null,
    roomName: '',
    gameType: 'human',
    difficulty: 'MEDIUM',
    currentPlayer: 'white',
    selectedCell: null,
    legalMoves: [],
    boardState: { pieces: [], legal_moves: [] },
    chatHistory: [],
    moveHistory: [],
    connected: false,
    ws: null
};

const ui = {
    statusBar: document.getElementById('statusBar'),
    roomList: document.getElementById('roomList'),
    createRoomButton: document.getElementById('createRoomButton'),
    refreshRoomsButton: document.getElementById('refreshRoomsButton'),
    gameType: document.getElementById('gameType'),
    difficultySelect: document.getElementById('difficultySelect'),
    gameArea: document.getElementById('gameArea'),
    roomNameText: document.getElementById('roomNameText'),
    roomPlayersText: document.getElementById('roomPlayersText'),
    turnText: document.getElementById('turnText'),
    gameStatusText: document.getElementById('gameStatusText'),
    chatHistory: document.getElementById('chatHistory'),
    moveHistory: document.getElementById('moveHistory'),
    chatInput: document.getElementById('chatInput'),
    sendChatButton: document.getElementById('sendChatButton'),
    chessBoard: document.getElementById('chessBoard'),
    boardContext: null,
};

const PIECE_UNICODE = {
    wp: '♙', wn: '♘', wb: '♗', wr: '♖', wq: '♕', wk: '♔',
    bp: '♟', bn: '♞', bb: '♝', br: '♜', bq: '♛', bk: '♚'
};

function init() {
    ui.boardContext = ui.chessBoard.getContext('2d');
    ui.createRoomButton.addEventListener('click', createRoom);
    ui.refreshRoomsButton.addEventListener('click', refreshRooms);
    ui.sendChatButton.addEventListener('click', sendChat);
    ui.chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            sendChat();
        }
    });
    ui.chessBoard.addEventListener('click', handleBoardClick);
    ui.gameType.addEventListener('change', () => {
        state.gameType = ui.gameType.value;
        ui.difficultySelect.disabled = state.gameType !== 'ai';
    });
    ui.difficultySelect.addEventListener('change', () => {
        state.difficulty = ui.difficultySelect.value;
    });
    updateStatus('Connecting to server...');
    connectWebSocket();
}

function connectWebSocket() {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname;
    const port = '8765';
    state.ws = new WebSocket(`${scheme}://${host}:${port}`);
    state.ws.addEventListener('open', onWebSocketOpen);
    state.ws.addEventListener('message', onWebSocketMessage);
    state.ws.addEventListener('close', onWebSocketClose);
    state.ws.addEventListener('error', onWebSocketError);
}

function onWebSocketOpen() {
    state.connected = true;
    updateStatus('Connected. Browse rooms or create a new match.');
    refreshRooms();
}

function onWebSocketMessage(event) {
    try {
        const message = JSON.parse(event.data);
        handleIncomingMessage(message);
    } catch (error) {
        console.error('Invalid message', error);
    }
}

function onWebSocketClose() {
    state.connected = false;
    updateStatus('Disconnected. Reconnect to continue.');
}

function onWebSocketError() {
    updateStatus('Connection error. Please refresh the page.');
}

function sendWebSocket(message) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(message));
    }
}

function handleIncomingMessage(message) {
    switch (message.type) {
        case 'board_update':
            applyBoardUpdate(message.room_state);
            break;
        case 'chat':
            appendChat(message.player_id, message.message);
            break;
        case 'player_joined':
            updateStatus(`Player joined room ${message.room_id}`);
            break;
        case 'player_left':
            updateStatus(`Player left room ${message.room_id}`);
            break;
        case 'spectator_joined':
            updateStatus(`A spectator joined ${message.room_id}`);
            break;
        case 'refresh_rooms':
            renderRoomList(message.rooms);
            break;
        case 'game_over':
            updateStatus(`Game over: ${message.status}`);
            break;
        case 'pong':
            break;
        case 'error':
            updateStatus(`Error: ${message.message}`);
            break;
        default:
            console.log('Unhandled message', message);
    }
}

function applyBoardUpdate(roomState) {
    state.roomId = roomState.room_id;
    state.roomName = roomState.room_name;
    state.boardState = roomState.board_state;
    state.currentPlayer = state.boardState.current_player;
    state.chatHistory = roomState.chat_history;
    state.moveHistory = roomState.move_history;
    ui.roomNameText.textContent = roomState.room_name;
    ui.roomPlayersText.textContent = `${roomState.players.length}/2`;
    ui.turnText.textContent = state.currentPlayer;
    ui.gameStatusText.textContent = roomState.status;
    ui.gameArea.style.display = 'grid';
    drawBoard();
    renderMoveHistory();
    renderChatHistory();
}

function appendChat(playerId, message) {
    const entry = document.createElement('div');
    entry.className = 'chat-message';
    entry.textContent = `${playerId}: ${message}`;
    ui.chatHistory.appendChild(entry);
    ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
}

function renderChatHistory() {
    ui.chatHistory.innerHTML = '';
    if (!Array.isArray(state.chatHistory)) {
        return;
    }
    state.chatHistory.forEach((entry) => {
        const row = document.createElement('div');
        row.className = 'chat-message';
        row.textContent = `${entry.player_id}: ${entry.message}`;
        ui.chatHistory.appendChild(row);
    });
    ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
}

function renderMoveHistory() {
    ui.moveHistory.innerHTML = '';
    if (!Array.isArray(state.moveHistory)) {
        return;
    }
    state.moveHistory.slice(-20).forEach((move) => {
        const row = document.createElement('div');
        row.className = 'history-event';
        row.textContent = `${move.player_id} ${move.uci}`;
        ui.moveHistory.appendChild(row);
    });
    ui.moveHistory.scrollTop = ui.moveHistory.scrollHeight;
}

function updateStatus(text) {
    ui.statusBar.textContent = text;
}

function renderRoomList(rooms) {
    ui.roomList.innerHTML = '';
    if (!Array.isArray(rooms) || rooms.length === 0) {
        ui.roomList.textContent = 'No rooms available. Create a new room to start playing.';
        return;
    }
    rooms.forEach((room) => {
        const card = document.createElement('div');
        card.className = 'room-card';
        const title = document.createElement('strong');
        title.textContent = room.room_name;
        const description = document.createElement('div');
        description.innerHTML = `Players: ${room.players}/2 • Status: ${room.status} • Type: ${room.game_type.toUpperCase()} ${room.game_type === 'ai' ? `• ${room.difficulty}` : ''}`;
        const idLine = document.createElement('small');
        idLine.textContent = `ID: ${room.room_id}`;
        const joinButton = document.createElement('button');
        joinButton.textContent = 'Join';
        joinButton.onclick = () => joinRoom(room.room_id);
        card.appendChild(title);
        card.appendChild(description);
        card.appendChild(idLine);
        card.appendChild(joinButton);
        ui.roomList.appendChild(card);
    });
}

function createRoom() {
    if (!state.connected) {
        updateStatus('Not connected. Please wait for connection.');
        return;
    }
    const roomName = prompt('Enter a room name:', 'Beginner Room');
    if (!roomName) {
        return;
    }
    const message = {
        type: 'create_room',
        player_id: state.playerId,
        room_name: roomName,
        game_type: state.gameType,
        difficulty: state.difficulty
    };
    sendWebSocket(message);
}

function joinRoom(roomId) {
    if (!state.connected) {
        updateStatus('Not connected. Please refresh.');
        return;
    }
    sendWebSocket({
        type: 'join_room',
        player_id: state.playerId,
        room_id: roomId
    });
}

function refreshRooms() {
    if (!state.connected) {
        return;
    }
    sendWebSocket({ type: 'refresh_rooms' });
}

function sendChat() {
    const text = ui.chatInput.value.trim();
    if (!text || !state.roomId) {
        return;
    }
    sendWebSocket({
        type: 'chat',
        player_id: state.playerId,
        room_id: state.roomId,
        message: text
    });
    ui.chatInput.value = '';
}

function handleBoardClick(event) {
    if (!state.roomId || !state.boardState) {
        return;
    }
    const rect = ui.chessBoard.getBoundingClientRect();
    const cellSize = rect.width / 8;
    const col = Math.floor((event.clientX - rect.left) / cellSize);
    const row = Math.floor((event.clientY - rect.top) / cellSize);
    const clicked = { row, col };

    const selectedPiece = state.boardState.pieces.find((piece) => piece.row === row && piece.col === col);
    if (state.selectedCell && isLegalTarget(clicked)) {
        attemptMove(state.selectedCell, clicked);
        state.selectedCell = null;
        state.legalMoves = [];
        drawBoard();
        return;
    }

    if (selectedPiece && selectedPiece.color === state.currentPlayer) {
        state.selectedCell = clicked;
        state.legalMoves = state.boardState.legal_moves.filter((move) => move.from_row === row && move.from_col === col);
        drawBoard();
        return;
    }

    state.selectedCell = null;
    state.legalMoves = [];
    drawBoard();
}

function isLegalTarget(cell) {
    return state.legalMoves.some((move) => move.to_row === cell.row && move.to_col === cell.col);
}

function attemptMove(from, to) {
    const move = state.legalMoves.find((move) => move.to_row === to.row && move.to_col === to.col);
    if (!move) {
        updateStatus('Illegal move selection');
        return;
    }
    sendWebSocket({
        type: 'move',
        player_id: state.playerId,
        room_id: state.roomId,
        from_row: from.row,
        from_col: from.col,
        to_row: to.row,
        to_col: to.col,
        promotion: move.promotion || undefined
    });
}

function drawBoard() {
    const ctx = ui.boardContext;
    const canvas = ui.chessBoard;
    const size = canvas.width;
    const cellSize = size / 8;

    ctx.clearRect(0, 0, size, size);

    for (let row = 0; row < 8; row += 1) {
        for (let col = 0; col < 8; col += 1) {
            ctx.fillStyle = (row + col) % 2 === 0 ? '#f0d9b5' : '#b58863';
            ctx.fillRect(col * cellSize, row * cellSize, cellSize, cellSize);
        }
    }

    if (state.selectedCell) {
        ctx.fillStyle = 'rgba(102, 201, 72, 0.45)';
        ctx.fillRect(state.selectedCell.col * cellSize, state.selectedCell.row * cellSize, cellSize, cellSize);
        state.legalMoves.forEach((move) => {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
            ctx.beginPath();
            ctx.arc((move.to_col + 0.5) * cellSize, (move.to_row + 0.5) * cellSize, cellSize * 0.14, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    state.boardState.pieces.forEach((piece) => {
        const x = piece.col * cellSize + cellSize / 2;
        const y = piece.row * cellSize + cellSize / 2;
        const key = `${piece.color[0]}${piece.type}`;
        const symbol = PIECE_UNICODE[key] || piece.type.toUpperCase();
        ctx.fillStyle = piece.color === 'white' ? '#ffffff' : '#121212';
        ctx.font = `${cellSize * 0.72}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(symbol, x, y);
    });
}

window.addEventListener('load', init);
