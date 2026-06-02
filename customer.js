/**
 * Production Chess Client - Full UI with game session management
 */

// ============ CLIENT STATE ============

const gameState = {
    sessionId: null,
    playerId: `player-${Date.now()}`,
    playerColor: null,  // 'white' or 'black'
    aiEnabled: false,
    isMyTurn: true,
    boardState: { pieces: [] },
    selectedSquare: null,
    legalMoves: [],
    status: 'Initializing...'
};

const ui = {
    canvas: document.getElementById('chessBoard'),
    ctx: null,
    statusEl: document.getElementById('status'),
    gameMenuEl: document.getElementById('gameMenu'),
    gameboardEl: document.getElementById('gameboard'),
    boardSize: 8,
    cellSize: 0
};

let ws = null;
let draggedPiece = null;
let dragOffset = { x: 0, y: 0 };

// ============ INITIALIZATION ============

function init() {
    ui.ctx = ui.canvas.getContext('2d');
    updateStatus('Connecting to server...');
    
    ws = new WebSocket(`ws://${window.location.hostname}:3401/ws`);
    ws.addEventListener('open', onWebSocketOpen);
    ws.addEventListener('message', onWebSocketMessage);
    ws.addEventListener('close', onWebSocketClose);
    ws.addEventListener('error', onWebSocketError);

    setupCanvasEvents();
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
}

// ============ WEBSOCKET HANDLERS ============

function onWebSocketOpen() {
    updateStatus('Connected! Create or join a game.');
    showGameMenu();
}

function onWebSocketMessage(event) {
    try {
        const message = JSON.parse(event.data);
        handleMessage(message);
    } catch (e) {
        console.error('Failed to parse message:', e);
    }
}

function onWebSocketClose() {
    updateStatus('Disconnected from server.');
    showGameMenu();
}

function onWebSocketError(error) {
    updateStatus('WebSocket error. Check console.');
    console.error('WebSocket error:', error);
}

function sendMessage(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
    }
}

// ============ MESSAGE HANDLERS ============

function handleMessage(message) {
    const handlers = {
        'game_start': handleGameStart,
        'board_update': handleBoardUpdate,
        'move_result': handleMoveResult,
        'check': handleCheck,
        'checkmate': handleCheckmate,
        'stalemate': handleStalemate,
        'list_games': handleListGames,
        'pong': () => {} // Heartbeat response
    };

    const handler = handlers[message.type];
    if (handler) {
        handler(message);
    } else {
        console.log('Unknown message type:', message.type);
    }
}

function handleGameStart(msg) {
    gameState.sessionId = msg.session_id;
    gameState.boardState = msg.session_state.board;
    gameState.aiEnabled = msg.session_state.ai_enabled;
    gameState.isMyTurn = msg.session_state.board.current_player === 'white';
    gameState.playerColor = 'white';
    
    updateStatus(`Game started! Your color: ${gameState.playerColor}`);
    showGameboard();
    drawBoard();
}

function handleBoardUpdate(msg) {
    gameState.boardState = msg.session_state.board;
    gameState.isMyTurn = msg.session_state.board.current_player === gameState.playerColor;
    
    updateStatus(`${gameState.boardState.current_player}'s turn`);
    drawBoard();
}

function handleMoveResult(msg) {
    if (!msg.success) {
        updateStatus(`Move failed: ${msg.error || 'Unknown error'}`);
        return;
    }

    updateStatus('Move accepted');

    // Handle AI move if present
    if (msg.ai_move) {
        updateStatus('AI is thinking...');
        setTimeout(() => {
            updateStatus('AI moved. Your turn.');
        }, 500);
    }
}

function handleCheck(msg) {
    updateStatus(`⚠️  CHECK!`);
}

function handleCheckmate(msg) {
    updateStatus(`CHECKMATE! ${msg.winner_color} wins!`);
}

function handleStalemate(msg) {
    updateStatus('STALEMATE - Draw!');
}

function handleListGames(msg) {
    console.log('Available games:', msg.games);
}

// ============ UI CONTROLS ============

function showGameMenu() {
    ui.gameMenuEl.style.display = 'block';
    ui.gameboardEl.style.display = 'none';
}

function showGameboard() {
    ui.gameMenuEl.style.display = 'none';
    ui.gameboardEl.style.display = 'block';
}

function createGame() {
    const difficulty = document.getElementById('difficulty')?.value || 'MEDIUM';
    sendMessage({
        type: 'create_game',
        player_id: gameState.playerId,
        ai_enabled: true,
        ai_difficulty: difficulty
    });
}

function playWithoutAI() {
    sendMessage({
        type: 'create_game',
        player_id: gameState.playerId,
        ai_enabled: false
    });
}

function updateStatus(text) {
    gameState.status = text;
    if (ui.statusEl) {
        ui.statusEl.textContent = text;
    }
}

// ============ CANVAS RENDERING ============

function resizeCanvas() {
    const size = Math.min(window.innerWidth, window.innerHeight) - 60;
    ui.canvas.width = size;
    ui.canvas.height = size;
    ui.cellSize = ui.canvas.width / ui.boardSize;
    drawBoard();
}

function drawBoard() {
    const { ctx, canvas, cellSize, boardSize } = ui;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw checkerboard
    for (let row = 0; row < boardSize; row++) {
        for (let col = 0; col < boardSize; col++) {
            ctx.fillStyle = (row + col) % 2 === 0 ? '#f0d9b5' : '#b58863';
            ctx.fillRect(col * cellSize, row * cellSize, cellSize, cellSize);
        }
    }

    // Draw coordinates
    ctx.fillStyle = '#666';
    ctx.font = '12px Arial';
    for (let i = 0; i < boardSize; i++) {
        ctx.fillText(String.fromCharCode(97 + i), i * cellSize + 4, canvas.height - 4);
        ctx.fillText(8 - i, 4, (i + 1) * cellSize - 4);
    }

    // Draw selected square highlight
    if (gameState.selectedSquare) {
        ctx.fillStyle = 'rgba(186, 202, 68, 0.5)';
        const sq = gameState.selectedSquare;
        ctx.fillRect(sq.col * cellSize, sq.row * cellSize, cellSize, cellSize);

        // Draw legal moves
        gameState.legalMoves.forEach(move => {
            ctx.fillStyle = 'rgba(186, 202, 68, 0.3)';
            ctx.beginPath();
            ctx.arc((move.col + 0.5) * cellSize, (move.row + 0.5) * cellSize, cellSize * 0.15, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    // Draw pieces
    gameState.boardState.pieces.forEach(piece => {
        drawPiece(piece);
    });
}

function drawPiece(piece) {
    const { ctx, cellSize } = ui;
    const x = piece.col * cellSize + cellSize / 2;
    const y = piece.row * cellSize + cellSize / 2;
    const radius = cellSize * 0.35;

    // Piece background
    ctx.fillStyle = piece.color === 'white' ? '#fff' : '#000';
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    // Piece border
    ctx.strokeStyle = piece.color === 'white' ? '#333' : '#ddd';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Piece symbol
    const symbols = {
        pawn: '♟',
        knight: '♞',
        bishop: '♝',
        rook: '♜',
        queen: '♛',
        king: '♚'
    };

    ctx.fillStyle = piece.color === 'white' ? '#000' : '#fff';
    ctx.font = 'bold 32px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(symbols[piece.type] || '?', x, y);
}

// ============ CANVAS EVENTS ============

function setupCanvasEvents() {
    ui.canvas.addEventListener('click', onCanvasClick);
    ui.canvas.addEventListener('mousemove', onCanvasMouseMove);
}

function getSquareFromEvent(event) {
    const rect = ui.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    return {
        row: Math.floor(y / ui.cellSize),
        col: Math.floor(x / ui.cellSize)
    };
}

function onCanvasClick(event) {
    if (!gameState.isMyTurn) {
        updateStatus('Not your turn!');
        return;
    }

    const square = getSquareFromEvent(event);
    const piece = getPieceAt(square.row, square.col);

    if (gameState.selectedSquare) {
        // Try to move selected piece
        if (isLegalMove(square)) {
            makeMove(gameState.selectedSquare, square);
        }
        gameState.selectedSquare = null;
        gameState.legalMoves = [];
    } else if (piece && piece.color === gameState.playerColor) {
        // Select piece
        gameState.selectedSquare = square;
        gameState.legalMoves = getLegalMovesFor(square);
    }

    drawBoard();
}

function onCanvasMouseMove(event) {
    // Optional: show hover effects
}

function getPieceAt(row, col) {
    return gameState.boardState.pieces.find(p => p.row === row && p.col === col);
}

function getLegalMovesFor(square) {
    const piece = getPieceAt(square.row, square.col);
    if (!piece) return [];

    // Calculate legal moves based on piece type
    // For now, show all adjacent squares as a placeholder
    const moves = [];
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            // Simple placeholder - in real implementation, validate against chess rules
            const target = getPieceAt(r, c);
            if (!target || target.color !== piece.color) {
                moves.push({ row: r, col: c });
            }
        }
    }
    return moves;
}

function isLegalMove(target) {
    return gameState.legalMoves.some(m => m.row === target.row && m.col === target.col);
}

function makeMove(from, to) {
    sendMessage({
        type: 'move',
        session_id: gameState.sessionId,
        from_row: from.row,
        from_col: from.col,
        to_row: to.row,
        to_col: to.col,
        promotion: null
    });

    gameState.isMyTurn = false;
    updateStatus('Move sent...');
}

// ============ STARTUP ============

document.addEventListener('DOMContentLoaded', init);
