# ♟️ Chess Engine - Production Edition

A fully refactored, production-grade chess application with AI, WebSocket networking, and clean modular architecture.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser (Client)                  │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Chess.html + customer.js (Game UI & Logic)        │ │
│  └────────────────────┬───────────────────────────────┘ │
│                       │ WebSocket (port 3401)            │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│                   Python Server                          │
├──────────────────────────────────────────────────────────┤
│  server.py (Main orchestrator)                           │
│  ├─ HTTPHandler (port 3400 - Serves HTML/CSS/JS)       │
│  └─ WSHandler (port 3401 - WebSocket protocol)         │
├──────────────────────────────────────────────────────────┤
│  Core Modules:                                           │
│  ├─ chess_engine.py (Full chess rules + FEN)           │
│  ├─ ai_engine.py (Minimax AI with difficulty)          │
│  ├─ game_session.py (Multi-game state management)       │
│  └─ network_protocol.py (Clean JSON event protocol)     │
└──────────────────────────────────────────────────────────┘
```

## Features

### ✅ Chess Engine
- **Full Rules Compliance**: Pawn promotion, castling, en passant, check/checkmate detection
- **FEN Notation**: Board state serialization and reconstruction
- **Legal Move Validation**: Server-side validation prevents cheating
- **Piece Movement**: All standard chess pieces with correct movement rules

### ✅ AI System
- **Minimax Algorithm**: With alpha-beta pruning for efficient search
- **Difficulty Levels**: Easy (random), Medium (depth 3), Hard (depth 5)
- **Position Evaluation**: Material counting + position bonuses + mobility
- **Server-side Only**: AI logic isolated on server, not trustedto client

### ✅ Networking
- **WebSocket Protocol**: Real-time bidirectional communication
- **Clean JSON API**: Structured message types with full payload validation
- **Multi-game Support**: Concurrent session management
- **Broadcast Updates**: Efficient state synchronization to all players

### ✅ Architecture
- **Modular Design**: Each component is isolated and testable
- **Separation of Concerns**: Game logic, AI, networking kept separate
- **Type Hints**: Python 3.11+ type annotations throughout
- **Thread Safety**: Lock-protected shared state for concurrent connections

### ✅ Safety & Validation
- **Server-side Move Validation**: Never trust client moves
- **Game State Integrity**: Prevents illegal state transitions
- **Session Management**: Proper player lifecycle handling
- **Error Handling**: Graceful failure for malformed messages

## File Structure

```
Chess thingy/
├── Chess.html              # Web UI (game menu + canvas)
├── customer.js             # Client-side game logic
├── server.py               # Main WebSocket/HTTP server
├── chess_engine.py         # Chess rules engine (~550 lines)
├── ai_engine.py            # Minimax AI with pruning (~200 lines)
├── game_session.py         # Game state & session manager (~180 lines)
├── network_protocol.py     # JSON protocol definitions (~140 lines)
└── README.md              # This file
```

## Installation & Running

### Requirements
- Python 3.11+
- No external dependencies (uses only stdlib)
- Modern web browser with WebSocket support

### Start Server

```bash
cd "Chess thingy"
python3 server.py
```

### Access Game

Open browser to: **http://localhost:3400/Chess.html**

## Network Protocol

### Message Types

#### 1. Game Lifecycle
```json
{
  "type": "create_game",
  "player_id": "player-1234567890",
  "ai_enabled": true,
  "ai_difficulty": "MEDIUM"
}
```

#### 2. Move Execution
```json
{
  "type": "move",
  "session_id": "uuid",
  "from_row": 6,
  "from_col": 4,
  "to_row": 4,
  "to_col": 4,
  "promotion": null
}
```

#### 3. Board Update (Server → Client)
```json
{
  "type": "board_update",
  "session_id": "uuid",
  "session_state": {
    "pieces": [...],
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "current_player": "white",
    "in_check": false,
    "checkmate": false,
    "stalemate": false
  }
}
```

#### 4. Game Over
```json
{
  "type": "checkmate",
  "session_id": "uuid",
  "winner_color": "white"
}
```

See `network_protocol.py` for complete protocol definition.

## Chess Engine Details

### Board Representation
- 8x8 2D array of Piece objects
- Piece: type (PAWN/KNIGHT/BISHOP/ROOK/QUEEN/KING) + color (WHITE/BLACK)
- Tracks: current player, en passant target, castling rights, move clocks

### Move Validation
1. **Pseudo-legal**: Check if piece can move according to its type
2. **Legal**: Verify move doesn't leave king in check
3. **Special Moves**: Handle castling, en passant, pawn promotion

### FEN Support
Example: `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`

## AI Engine Details

### Algorithm
```
minimax(board, depth, alpha, beta, isMaximizing):
  if depth == 0 or game_over:
    return evaluate_position(board)
  
  if isMaximizing:
    for each legal_move:
      value = minimax(make_move, depth-1, alpha, beta, false)
      alpha = max(alpha, value)
      if beta <= alpha: break  # Alpha-beta pruning
    return alpha
  else:
    similar for minimizing player
```

### Position Evaluation
- **Material**: Piece values (Pawn=1, Knight=3, Bishop=3.3, Rook=5, Queen=9)
- **Position**: Center control bonuses, pawn advancement
- **Mobility**: Number of legal moves available
- **King Safety**: Check/checkmate detection

### Difficulty Levels
- **Easy**: Random move selection
- **Medium**: Depth 3 minimax (reasonable play)
- **Hard**: Depth 5 minimax (challenging play)

## Game Session Management

### Session Lifecycle
1. **Create**: Player initiates game, gets session UUID
2. **Join**: Second player joins waiting session (optional)
3. **Play**: Alternating turns, moves broadcast to all players
4. **End**: Checkmate, stalemate, or abandonment

### State Tracking
- Move history (full move notation)
- FEN string at each position
- Connected players
- Game status enum

## Validation & Safety

### Server-side Checks
- ✅ Player must own piece (if opponent move)
- ✅ Move must be legal per chess rules
- ✅ Must be player's turn
- ✅ Cannot leave king in check
- ✅ Promotion piece must be valid
- ✅ No moves after game ends

### Client Restrictions
- Move execution only via WebSocket
- Server responds with authoritative board state
- No local board modification possible

## Performance Optimizations

### Alpha-Beta Pruning
Reduces search space from ~B^d to ~B^(d/2), where B=avg branching factor, d=depth

### Transposition Table
Caches evaluated positions to avoid re-computation (can be extended)

### Broadcast Efficiency
- Only sends board state diffs
- Minimal JSON payload
- Targeted broadcasting per session

## Future Enhancements

- [ ] Extended transposition table (save to disk)
- [ ] Opening book (pre-computed strong opening moves)
- [ ] Endgame tablebases (perfect play in simplified positions)
- [ ] Network persistence (player statistics, replay games)
- [ ] Spectator mode (watch games without playing)
- [ ] Time controls (bullet, blitz, rapid, classical)
- [ ] Elo rating system for matchmaking
- [ ] WebRTC peer-to-peer for local multiplayer

## Testing

### Unit Tests (Manual)
```bash
python3 << 'EOF'
from chess_engine import ChessBoard, Color

board = ChessBoard()

# Test move
board.make_move(6, 4, 4, 4)  # Pawn e2-e4
print(f"After move: {board.board[4][4]}")
print(f"FEN: {board.get_fen()}")
print(f"Current player: {board.current_player.value}")
EOF
```

### Integration Tests
1. Start server
2. Open http://localhost:3400/Chess.html
3. Create game with AI
4. Make moves and verify AI responds
5. Play to checkmate

## Debugging

### Server Logs
```
🌐 HTTP server running on http://localhost:3400
♟️  WebSocket server running on ws://localhost:3401
[player-id] is connected
```

### Browser Console
- WebSocket connect/disconnect events
- Message send/receive logging
- Board state changes

### Python Debugging
```bash
# Run server with verbose logging
python3 -u server.py
```

## License & Attribution

Created as a complete refactor of a simple chess demo into a production-grade application.

Pure Python implementation (no external libraries) for maximum portability.

---

**Version**: 1.0 (Production Edition)  
**Python**: 3.11+  
**Updated**: May 2026
