# API Reference - Production Chess Server

## WebSocket Protocol

### Connection
```
ws://localhost:3401/ws
```

---

## Message Format

All messages are JSON:
```json
{
  "type": "message_type",
  "payload": { /* optional */ }
}
```

---

## Client → Server Messages

### 1. Create Game
```json
{
  "type": "create_game",
  "player_id": "optional-string",
  "ai_enabled": false,
  "ai_difficulty": "EASY|MEDIUM|HARD"
}
```
**Response**: `game_start` message with session state

---

### 2. Join Game
```json
{
  "type": "join_game",
  "player_id": "optional-string",
  "session_id": "uuid"
}
```
**Response**: `game_start` message with session state  
**Error**: No response if game unavailable

---

### 3. List Available Games
```json
{
  "type": "list_games"
}
```
**Response**:
```json
{
  "type": "list_games",
  "games": [
    {
      "session_id": "uuid",
      "status": "waiting",
      "ai_enabled": false,
      "player_id": "creator-id"
    }
  ]
}
```

---

### 4. Make Move
```json
{
  "type": "move",
  "session_id": "uuid",
  "from_row": 6,
  "from_col": 4,
  "to_row": 4,
  "to_col": 4,
  "promotion": "Q|R|B|N|null"
}
```

**Success Response**:
```json
{
  "type": "move_result",
  "success": true,
  "error": null,
  "ai_move": {
    "from_row": 1,
    "from_col": 4,
    "to_row": 3,
    "to_col": 4
  }
}
```

**Followed by**: `board_update` message

**Failure Response**:
```json
{
  "type": "move_result",
  "success": false,
  "error": "Illegal move"
}
```

---

### 5. Ping (Keep-Alive)
```json
{
  "type": "ping"
}
```
**Response**:
```json
{
  "type": "pong"
}
```

---

## Server → Client Messages

### 1. Game Start
Sent when game begins (both players connected)
```json
{
  "type": "game_start",
  "session_id": "uuid",
  "session_state": {
    "board": {
      "pieces": [
        {
          "type": "pawn",
          "color": "white",
          "row": 6,
          "col": 0
        }
      ],
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "current_player": "white",
      "in_check": false,
      "checkmate": false,
      "stalemate": false
    },
    "ai_enabled": false,
    "move_history": []
  }
}
```

---

### 2. Board Update
Sent after each move
```json
{
  "type": "board_update",
  "session_id": "uuid",
  "session_state": { /* same as game_start */ }
}
```

---

### 3. Check
```json
{
  "type": "check",
  "session_id": "uuid"
}
```

---

### 4. Checkmate
```json
{
  "type": "checkmate",
  "session_id": "uuid",
  "winner_color": "white|black"
}
```

---

### 5. Stalemate
```json
{
  "type": "stalemate",
  "session_id": "uuid"
}
```

---

## Board Representation

### Piece Object
```json
{
  "type": "pawn|knight|bishop|rook|queen|king",
  "color": "white|black",
  "row": 0-7,
  "col": 0-7
}
```

### Row/Column Convention
- **Row 0**: Black's back rank
- **Row 7**: White's back rank
- **Col 0**: A-file (queenside)
- **Col 7**: H-file (kingside)

### FEN String Format
```
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
```
- Position / Active color / Castling / En passant / Halfmove clock / Fullmove number

---

## Error Codes

| Error | Meaning |
|-------|---------|
| "Not in a game" | Player not connected to session |
| "Invalid move format" | Missing required move fields |
| "Illegal move" | Move violates chess rules |
| "Not your turn" | Other player's turn |
| "Game already started" | Cannot join full game |

---

## Session State Object

```json
{
  "session_id": "uuid",
  "status": "waiting|in_progress|checkmate|stalemate|draw|abandoned",
  "board": { /* board state */ },
  "player_id": "original-creator-id",
  "ai_enabled": true|false,
  "ai_difficulty": "EASY|MEDIUM|HARD|null",
  "move_history": [
    {
      "from": [6, 4],
      "to": [4, 4],
      "promotion": null,
      "fen": "..."
    }
  ],
  "connected_clients": ["player-id1", "player-id2"]
}
```

---

## Example Game Flow

1. **Client connects** → WebSocket `open` event

2. **Create game**
   - Client sends: `create_game`
   - Server responds: `game_start`

3. **Player makes move**
   - Client sends: `move`
   - Server validates move
   - Server applies move
   - If AI enabled: Server computes AI move
   - Server sends: `move_result` + `board_update`
   - Server broadcasts: `board_update` to all players

4. **Game ends**
   - Server detects: checkmate/stalemate
   - Server broadcasts: `checkmate` or `stalemate`

5. **Disconnect**
   - Client closes connection → WebSocket `close` event
   - Server removes player from session

---

## Implementation Notes

### Move Validation Pipeline
1. Parse move JSON
2. Verify player in session
3. Verify it's player's turn
4. Call `chess_engine.get_legal_moves(row, col)`
5. Verify target square in legal moves
6. Execute move with `make_move()`
7. Check game status
8. Broadcast update

### AI Decision Process
1. Get all legal moves for AI color
2. For each move:
   - Simulate board state
   - Run minimax(depth=3, alpha=-inf, beta=+inf, maximizing=true)
   - Track best score and move
3. Return best move
4. Validate and apply move
5. Send AI move in `move_result`

### Turn System
- White always moves first
- After white's move: `current_player` = "black"
- After black's move: `current_player` = "white"
- Client checks `board.current_player == player_color` to enable UI

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Minimax search (depth 3) | ~100-500ms |
| Minimax search (depth 5) | ~1-5s |
| Board state serialization | <1ms |
| WebSocket frame overhead | ~2-4 bytes per message |
| Typical board update size | 2-4 KB JSON |

---

## Troubleshooting

### "Address already in use"
- Previous server still running
- Solution: `pkill -f "python3 server.py"`

### "Illegal move" despite valid move
- Check: `board.get_legal_moves(row, col)` server-side
- Verify: No piece pinned to king
- Verify: Move doesn't leave king in check

### AI takes too long
- Increase difficulty causes exponential slowdown
- Depth 5 can take 5+ seconds
- Solution: Reduce difficulty or implement better pruning

### WebSocket won't connect
- Verify server is running: `python3 server.py`
- Check ports open: ports 3400 (HTTP) and 3401 (WebSocket)
- Browser security: May need HTTPS in production

---

Generated: May 2026  
Version: 1.0 (Production Edition)
