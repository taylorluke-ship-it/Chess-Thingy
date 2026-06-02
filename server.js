// Imports Express framework (web server for Node.js)
const express = require('express');

// Imports path utilities (file path handling)
const path = require('path');

// Creates Express app instance
const app = express();

// Creates raw HTTP server (needed for Socket.IO integration)
const server = require('http').createServer(app);

// Attaches Socket.IO to HTTP server for real-time communication
const io = require('socket.io')(server);

// Port for server (env PORT or fallback 3400)
const PORT = process.env.PORT || 3400;

// Serves all files in current directory (HTML, JS, CSS, etc.)
app.use(express.static(__dirname));

// Route for homepage
app.get('/', (req, res) => {

    // trigger == user visits http://localhost:3400/
    res.sendFile(path.join(__dirname, 'Chess.html'));
});

// Logs server startup (does NOT affect logic)
console.log('My Socket Server is Running');



// Game state stored on server (authoritative source)
const boardState = [

    // Black pawns row
    { id: 'b-p1', type: 'pawn', color: 'black', row: 1, col: 0 },
    { id: 'b-p2', type: 'pawn', color: 'black', row: 1, col: 1 },
    { id: 'b-p3', type: 'pawn', color: 'black', row: 1, col: 2 },
    { id: 'b-p4', type: 'pawn', color: 'black', row: 1, col: 3 },
    { id: 'b-p5', type: 'pawn', color: 'black', row: 1, col: 4 },
    { id: 'b-p6', type: 'pawn', color: 'black', row: 1, col: 5 },
    { id: 'b-p7', type: 'pawn', color: 'black', row: 1, col: 6 },
    { id: 'b-p8', type: 'pawn', color: 'black', row: 1, col: 7 },

    // White pawns row
    { id: 'w-p1', type: 'pawn', color: 'white', row: 6, col: 0 },
    { id: 'w-p2', type: 'pawn', color: 'white', row: 6, col: 1 },
    { id: 'w-p3', type: 'pawn', color: 'white', row: 6, col: 2 },
    { id: 'w-p4', type: 'pawn', color: 'white', row: 6, col: 3 },
    { id: 'w-p5', type: 'pawn', color: 'white', row: 6, col: 4 },
    { id: 'w-p6', type: 'pawn', color: 'white', row: 6, col: 5 },
    { id: 'w-p7', type: 'pawn', color: 'white', row: 6, col: 6 },
    { id: 'w-p8', type: 'pawn', color: 'white', row: 6, col: 7 },

    // Example rook pieces
    { id: 'b-r1', type: 'rook', color: 'black', row: 0, col: 0 },
    { id: 'w-r1', type: 'rook', color: 'white', row: 7, col: 7 }
];



// Socket.IO connection handler
io.on('connection', socket => {

    // trigger == new client connects
    console.log(socket.id, 'is connected');

    // Send initial board state to client
    socket.emit('boardState', boardState);

    // Send welcome/info message to client
    socket.emit('message', 'Board loaded. Drag a piece to move it');



    // Handles piece movement from client
    socket.on('movePiece', data => {

        // Find piece being moved
        const piece = boardState.find(item => item.id === data.id);
        if (!piece) return;

        // Check if another piece exists at target square
        const targetIndex = boardState.findIndex(
            item => item.row === data.row && item.col === data.col
        );

        // If enemy piece exists, remove it (capture logic)
        if (targetIndex !== -1 && boardState[targetIndex].id !== piece.id) {
            boardState.splice(targetIndex, 1);
        }

        // Update piece position
        piece.row = data.row;
        piece.col = data.col;

        // Broadcast updated board to ALL clients
        io.emit('boardState', boardState);
    });



    // Handles client disconnect
    socket.on('disconnect', () => {

        // trigger == user closes tab / loses connection
        console.log(socket.id, 'disconnected');
    });
});



// Starts HTTP + Socket.IO server
server.listen(PORT, () => {

    // trigger == server successfully starts
    console.log('Server listening on http://localhost:' + PORT);
});