"""
Game Session Manager - Handles multiple concurrent games
"""

import uuid
from typing import Dict, Optional, List
from enum import Enum
from chess_engine import ChessBoard, Color
from ai_engine import AIEngine, Difficulty


class GameStatus(Enum):
    WAITING = 'waiting'
    IN_PROGRESS = 'in_progress'
    CHECKMATE = 'checkmate'
    STALEMATE = 'stalemate'
    DRAW = 'draw'
    ABANDONED = 'abandoned'


class GameSession:
    def __init__(self, session_id: str, player_id: str, ai_enabled: bool = False, ai_difficulty: Difficulty = Difficulty.MEDIUM):
        self.session_id = session_id
        self.player_id = player_id
        self.ai_enabled = ai_enabled
        self.ai_difficulty = ai_difficulty
        self.board = ChessBoard()
        self.ai_engine = AIEngine(ai_difficulty) if ai_enabled else None
        self.status = GameStatus.IN_PROGRESS if ai_enabled else GameStatus.WAITING
        self.move_history = []
        self.connected_clients = {player_id}
        self.created_at = None
        self.last_activity = None
        self.chat_history = []

    def add_player(self, player_id: str) -> bool:
        """Add second player to game"""
        if len(self.connected_clients) >= 2:
            return False
        self.connected_clients.add(player_id)
        if len(self.connected_clients) == 2:
            self.status = GameStatus.IN_PROGRESS
        return True

    def remove_player(self, player_id: str):
        """Remove player from game"""
        self.connected_clients.discard(player_id)
        if not self.connected_clients:
            self.status = GameStatus.ABANDONED

    def make_move(self, from_row: int, from_col: int, to_row: int, to_col: int, promotion: Optional[str] = None) -> bool:
        """Make a move in the game"""
        if self.status != GameStatus.IN_PROGRESS:
            return False

        if not self.board.make_move(from_row, from_col, to_row, to_col, promotion):
            return False

        # Record move
        self.move_history.append({
            'from': (from_row, from_col),
            'to': (to_row, to_col),
            'promotion': promotion,
            'fen': self.board.get_fen()
        })

        # Check game status
        if self.board.is_checkmate():
            self.status = GameStatus.CHECKMATE
        elif self.board.is_stalemate():
            self.status = GameStatus.STALEMATE

        return True

    def get_ai_move(self) -> Optional[tuple]:
        """Get AI move if enabled"""
        if not self.ai_enabled or not self.ai_engine:
            return None

        if self.board.current_player != Color.BLACK:
            return None

        return self.ai_engine.get_best_move(self.board)

    def get_state(self) -> Dict:
        """Get current game state"""
        return {
            'session_id': self.session_id,
            'status': self.status.value,
            'board': self.board.to_dict(),
            'player_id': self.player_id,
            'ai_enabled': self.ai_enabled,
            'ai_difficulty': self.ai_difficulty.name if self.ai_enabled else None,
            'move_history': self.move_history,
            'connected_clients': list(self.connected_clients)
        }


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, GameSession] = {}
        self.player_sessions: Dict[str, str] = {}  # player_id -> session_id

    def create_session(self, player_id: str, ai_enabled: bool = False, ai_difficulty: str = 'MEDIUM') -> str:
        """Create new game session"""
        session_id = str(uuid.uuid4())
        difficulty = Difficulty[ai_difficulty] if ai_enabled else Difficulty.MEDIUM
        session = GameSession(session_id, player_id, ai_enabled, difficulty)
        self.sessions[session_id] = session
        self.player_sessions[player_id] = session_id
        return session_id

    def join_session(self, session_id: str, player_id: str) -> bool:
        """Join existing game session"""
        session = self.sessions.get(session_id)
        if not session or session.status != GameStatus.WAITING:
            return False
        if session.add_player(player_id):
            self.player_sessions[player_id] = session_id
            return True
        return False

    def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def get_player_session(self, player_id: str) -> Optional[GameSession]:
        """Get player's current session"""
        session_id = self.player_sessions.get(player_id)
        return self.sessions.get(session_id) if session_id else None

    def make_move(self, session_id: str, player_id: str, from_row: int, from_col: int, to_row: int, to_col: int, promotion: Optional[str] = None) -> bool:
        """Make move in session"""
        session = self.sessions.get(session_id)
        if not session or player_id not in session.connected_clients:
            return False

        # Verify it's player's turn
        expected_color = Color.WHITE if len(session.move_history) % 2 == 0 else Color.BLACK

        # In AI games, player is always white
        if session.ai_enabled and expected_color == Color.BLACK:
            return False

        return session.make_move(from_row, from_col, to_row, to_col, promotion)

    def list_active_sessions(self) -> List[Dict]:
        """List all active sessions"""
        return [session.get_state() for session in self.sessions.values() if session.status == GameStatus.WAITING]

    def cleanup_abandoned(self):
        """Remove abandoned sessions"""
        self.sessions = {
            sid: session
            for sid, session in self.sessions.items()
            if session.status != GameStatus.ABANDONED
        }
