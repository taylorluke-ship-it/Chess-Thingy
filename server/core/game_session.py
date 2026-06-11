"""
Purpose
Responsibilities
Dependencies

Encapsulates game session state, move validation, player management, AI handoff, and room isolation.
"""

import chess
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .chess_engine import ChessGame
from .fallback_ai import FallbackAI
from .stockfish_engine import StockfishEngine
from .logger import logger


class GameStatus(Enum):
    WAITING = 'waiting'
    IN_PROGRESS = 'in_progress'
    CHECKMATE = 'checkmate'
    STALEMATE = 'stalemate'
    DRAW = 'draw'
    ABANDONED = 'abandoned'


class GameSession:
    """Represents a single isolated chess room and its gameplay state."""

    def __init__(
        self,
        room_id: str,
        room_name: str,
        host_id: str,
        game_type: str = 'human',
        difficulty: str = 'MEDIUM'
    ) -> None:
        self.room_id = room_id
        self.room_name = room_name
        self.host_id = host_id
        self.game_type = game_type
        self.difficulty = difficulty.upper() if difficulty else 'MEDIUM'
        self.players: List[str] = [host_id]
        self.spectators: Set[str] = set()
        self.chat_history: List[Dict[str, Any]] = []
        self.move_history: List[Dict[str, Any]] = []
        self.board = ChessGame()
        self.status = GameStatus.WAITING
        self.created_at = datetime.datetime.utcnow().isoformat() + 'Z'
        self.updated_at = self.created_at
        self.last_activity = self.created_at
        self.host_color = 'white'
        self.ai_enabled = self.game_type == 'ai'

    def touch(self) -> None:
        self.last_activity = datetime.datetime.utcnow().isoformat() + 'Z'
        self.updated_at = self.last_activity

    def add_player(self, player_id: str) -> bool:
        if player_id in self.players:
            return True
        if len(self.players) >= 2:
            return False
        self.players.append(player_id)
        if len(self.players) == 2:
            self.status = GameStatus.IN_PROGRESS
        self.touch()
        return True

    def remove_player(self, player_id: str) -> None:
        if player_id in self.players:
            self.players.remove(player_id)
        if player_id in self.spectators:
            self.spectators.discard(player_id)
        if not self.players:
            self.status = GameStatus.ABANDONED
        if self.host_id == player_id and self.players:
            self.host_id = self.players[0]
        self.touch()

    def add_spectator(self, spectator_id: str) -> bool:
        if spectator_id in self.players:
            return False
        self.spectators.add(spectator_id)
        self.touch()
        return True

    def is_player_turn(self, player_id: str) -> bool:
        if self.ai_enabled and player_id == self.host_id:
            return self.board.board.turn == True
        if player_id not in self.players:
            return False
        index = self.players.index(player_id)
        expected_color = 'white' if index == 0 else 'black'
        return expected_color == ('white' if self.board.board.turn else 'black')

    def get_room_summary(self) -> Dict[str, Any]:
        return {
            'room_id': self.room_id,
            'room_name': self.room_name,
            'host_id': self.host_id,
            'players': len(self.players),
            'capacity': 2,
            'status': self.status.value,
            'game_type': self.game_type,
            'difficulty': self.difficulty,
            'created_at': self.created_at
        }

    def add_chat_message(self, player_id: str, message: str) -> None:
        self.chat_history.append({
            'player_id': player_id,
            'message': message,
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z'
        })
        self.touch()

    def _update_status_after_move(self) -> None:
        result = self.board.get_result()
        if result == 'checkmate':
            self.status = GameStatus.CHECKMATE
        elif result == 'stalemate':
            self.status = GameStatus.STALEMATE
        elif result in ('insufficient_material', 'seventyfive_moves', 'fivefold_repetition'):
            self.status = GameStatus.DRAW
        elif self.status == GameStatus.WAITING:
            self.status = GameStatus.IN_PROGRESS

    async def make_move(self, player_id: str, from_row: int, from_col: int, to_row: int, to_col: int, promotion: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        self.touch()
        if self.status in (GameStatus.CHECKMATE, GameStatus.STALEMATE, GameStatus.DRAW, GameStatus.ABANDONED):
            return False, 'Game is already over'
        if not self.is_player_turn(player_id):
            return False, 'Not your turn'
        success, error = self.board.apply_move(from_row, from_col, to_row, to_col, promotion)
        if not success:
            return False, error
        self.move_history.append({
            'player_id': player_id,
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col,
            'promotion': promotion,
            'uci': self.board.history[-1]['uci'],
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z'
        })
        self._update_status_after_move()
        return True, None

    async def request_ai_move(self, stockfish: StockfishEngine, fallback: FallbackAI) -> Optional[Dict[str, Any]]:
        if not self.ai_enabled or self.status != GameStatus.IN_PROGRESS:
            return None
        if self.board.board.turn != chess.BLACK:
            return None
        move = await stockfish.get_best_move(self.board.board.fen(), self.difficulty)
        if not move:
            move = fallback.choose_move(self.board)
            logger.info('AI_ENGINE', 'Using fallback AI move', room_id=self.room_id)
        if not move:
            return None
        from_row, from_col, to_row, to_col, promotion = move
        success, error = await self.make_move(self.host_id, from_row, from_col, to_row, to_col, promotion)
        if not success:
            logger.error('AI_ENGINE', f'AI move failed: {error}', room_id=self.room_id)
            return None
        return {
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col,
            'promotion': promotion
        }

    def serialize(self) -> Dict[str, Any]:
        return {
            'room_id': self.room_id,
            'room_name': self.room_name,
            'host_id': self.host_id,
            'players': list(self.players),
            'spectators': list(self.spectators),
            'chat_history': list(self.chat_history),
            'move_history': list(self.move_history),
            'board_state': self.board.get_state(),
            'status': self.status.value,
            'game_type': self.game_type,
            'difficulty': self.difficulty,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_activity': self.last_activity
        }
