"""
Network Protocol - Defines all JSON message types and structures
"""

from enum import Enum
from typing import Dict, Any, Optional


class MessageType(Enum):
    # Game lifecycle
    CREATE_GAME = 'create_game'
    JOIN_GAME = 'join_game'
    LIST_GAMES = 'list_games'
    GAME_START = 'game_start'

    # Moves and updates
    MOVE = 'move'
    MOVE_RESULT = 'move_result'
    BOARD_UPDATE = 'board_update'

    # Game status
    GAME_OVER = 'game_over'
    CHECK = 'check'
    CHECKMATE = 'checkmate'
    STALEMATE = 'stalemate'

    # Connection
    PING = 'ping'
    PONG = 'pong'
    DISCONNECT = 'disconnect'

    # Chat
    CHAT = 'chat'


class Protocol:
    """Message protocol helper"""

    @staticmethod
    def create_game(player_id: str, ai_enabled: bool = False, ai_difficulty: str = 'MEDIUM') -> Dict[str, Any]:
        return {
            'type': MessageType.CREATE_GAME.value,
            'player_id': player_id,
            'ai_enabled': ai_enabled,
            'ai_difficulty': ai_difficulty
        }

    @staticmethod
    def join_game(player_id: str, session_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.JOIN_GAME.value,
            'player_id': player_id,
            'session_id': session_id
        }

    @staticmethod
    def list_games() -> Dict[str, Any]:
        return {
            'type': MessageType.LIST_GAMES.value
        }

    @staticmethod
    def game_start(session_id: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': MessageType.GAME_START.value,
            'session_id': session_id,
            'session_state': session_state
        }

    @staticmethod
    def make_move(session_id: str, from_row: int, from_col: int, to_row: int, to_col: int, promotion: Optional[str] = None) -> Dict[str, Any]:
        return {
            'type': MessageType.MOVE.value,
            'session_id': session_id,
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col,
            'promotion': promotion
        }

    @staticmethod
    def move_result(success: bool, error: Optional[str] = None, ai_move: Optional[tuple] = None) -> Dict[str, Any]:
        return {
            'type': MessageType.MOVE_RESULT.value,
            'success': success,
            'error': error,
            'ai_move': {
                'from_row': ai_move[0],
                'from_col': ai_move[1],
                'to_row': ai_move[2],
                'to_col': ai_move[3]
            } if ai_move else None
        }

    @staticmethod
    def board_update(session_id: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': MessageType.BOARD_UPDATE.value,
            'session_id': session_id,
            'session_state': session_state
        }

    @staticmethod
    def game_over(session_id: str, status: str, winner: Optional[str] = None) -> Dict[str, Any]:
        return {
            'type': MessageType.GAME_OVER.value,
            'session_id': session_id,
            'status': status,
            'winner': winner
        }

    @staticmethod
    def check(session_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.CHECK.value,
            'session_id': session_id
        }

    @staticmethod
    def checkmate(session_id: str, winner_color: str) -> Dict[str, Any]:
        return {
            'type': MessageType.CHECKMATE.value,
            'session_id': session_id,
            'winner_color': winner_color
        }

    @staticmethod
    def stalemate(session_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.STALEMATE.value,
            'session_id': session_id
        }

    @staticmethod
    def ping() -> Dict[str, Any]:
        return {
            'type': MessageType.PING.value
        }

    @staticmethod
    def pong() -> Dict[str, Any]:
        return {
            'type': MessageType.PONG.value
        }

    @staticmethod
    def chat(session_id: str, player_id: str, message: str) -> Dict[str, Any]:
        return {
            'type': MessageType.CHAT.value,
            'session_id': session_id,
            'player_id': player_id,
            'message': message
        }
