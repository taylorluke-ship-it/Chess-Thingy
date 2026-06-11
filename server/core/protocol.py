"""
Purpose
Responsibilities
Dependencies

Defines the JSON WebSocket protocol used by the chess application and validates incoming packets.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MessageType(Enum):
    CREATE_ROOM = 'create_room'
    JOIN_ROOM = 'join_room'
    LEAVE_ROOM = 'leave_room'
    REFRESH_ROOMS = 'refresh_rooms'
    START_GAME = 'start_game'
    MOVE = 'move'
    BOARD_UPDATE = 'board_update'
    CHAT = 'chat'
    GAME_OVER = 'game_over'
    PLAYER_JOINED = 'player_joined'
    PLAYER_LEFT = 'player_left'
    SPECTATOR_JOINED = 'spectator_joined'
    ERROR = 'error'
    HEARTBEAT = 'heartbeat'
    PONG = 'pong'


class Protocol:
    """Helper for creating and validating protocol messages."""

    REQUIRED_FIELDS = {
        MessageType.CREATE_ROOM.value: ['player_id', 'room_name', 'game_type'],
        MessageType.JOIN_ROOM.value: ['player_id', 'room_id'],
        MessageType.LEAVE_ROOM.value: ['player_id', 'room_id'],
        MessageType.START_GAME.value: ['player_id', 'room_id'],
        MessageType.MOVE.value: ['player_id', 'room_id', 'from_row', 'from_col', 'to_row', 'to_col'],
        MessageType.CHAT.value: ['player_id', 'room_id', 'message'],
        MessageType.REFRESH_ROOMS.value: [],
        MessageType.HEARTBEAT.value: [],
    }

    OPTIONAL_FIELDS = {
        MessageType.CREATE_ROOM.value: ['difficulty'],
        MessageType.MOVE.value: ['promotion'],
    }

    @staticmethod
    def _validate_fields(message: Dict[str, Any], required: List[str], optional: List[str]) -> Tuple[bool, Optional[str]]:
        for field in required:
            if field not in message:
                return False, f"Missing required field '{field}'"
        for field in message:
            if field not in required and field not in optional and field != 'type':
                return False, f"Unexpected field '{field}'"
        return True, None

    @classmethod
    def validate_message(cls, payload: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not isinstance(payload, dict):
            return None, 'Invalid packet structure'

        message_type = payload.get('type')
        if not message_type or message_type not in [item.value for item in MessageType]:
            return None, 'Invalid or missing message type'

        required = cls.REQUIRED_FIELDS.get(message_type, [])
        optional = cls.OPTIONAL_FIELDS.get(message_type, [])
        valid, error = cls._validate_fields(payload, required, optional)
        if not valid:
            return None, error
        return payload, None

    @staticmethod
    def create_room(player_id: str, room_name: str, game_type: str, difficulty: Optional[str] = None) -> Dict[str, Any]:
        message = {
            'type': MessageType.CREATE_ROOM.value,
            'player_id': player_id,
            'room_name': room_name,
            'game_type': game_type
        }
        if difficulty:
            message['difficulty'] = difficulty
        return message

    @staticmethod
    def join_room(player_id: str, room_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.JOIN_ROOM.value,
            'player_id': player_id,
            'room_id': room_id
        }

    @staticmethod
    def leave_room(player_id: str, room_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.LEAVE_ROOM.value,
            'player_id': player_id,
            'room_id': room_id
        }

    @staticmethod
    def refresh_rooms() -> Dict[str, Any]:
        return {'type': MessageType.REFRESH_ROOMS.value}

    @staticmethod
    def start_game(player_id: str, room_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.START_GAME.value,
            'player_id': player_id,
            'room_id': room_id
        }

    @staticmethod
    def move(
        player_id: str,
        room_id: str,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
        promotion: Optional[str] = None
    ) -> Dict[str, Any]:
        message = {
            'type': MessageType.MOVE.value,
            'player_id': player_id,
            'room_id': room_id,
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col
        }
        if promotion:
            message['promotion'] = promotion
        return message

    @staticmethod
    def board_update(room_id: str, room_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type': MessageType.BOARD_UPDATE.value,
            'room_id': room_id,
            'room_state': room_state
        }

    @staticmethod
    def chat(room_id: str, player_id: str, message: str) -> Dict[str, Any]:
        return {
            'type': MessageType.CHAT.value,
            'room_id': room_id,
            'player_id': player_id,
            'message': message
        }

    @staticmethod
    def player_joined(room_id: str, player_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.PLAYER_JOINED.value,
            'room_id': room_id,
            'player_id': player_id
        }

    @staticmethod
    def player_left(room_id: str, player_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.PLAYER_LEFT.value,
            'room_id': room_id,
            'player_id': player_id
        }

    @staticmethod
    def spectator_joined(room_id: str, spectator_id: str) -> Dict[str, Any]:
        return {
            'type': MessageType.SPECTATOR_JOINED.value,
            'room_id': room_id,
            'spectator_id': spectator_id
        }

    @staticmethod
    def error(message: str, code: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            'type': MessageType.ERROR.value,
            'message': message
        }
        if code:
            payload['code'] = code
        return payload

    @staticmethod
    def game_over(room_id: str, status: str, winner: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            'type': MessageType.GAME_OVER.value,
            'room_id': room_id,
            'status': status
        }
        if winner:
            payload['winner'] = winner
        return payload

    @staticmethod
    def heartbeat() -> Dict[str, Any]:
        return {'type': MessageType.HEARTBEAT.value}

    @staticmethod
    def pong() -> Dict[str, Any]:
        return {'type': MessageType.PONG.value}
