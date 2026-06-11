"""
Purpose
Responsibilities
Dependencies

Maintains isolated room state, player membership, spectators, rejoin handling, and cleanup.
"""

import asyncio
import datetime
import time
import uuid
from typing import Dict, List, Optional

from .game_session import GameSession, GameStatus
from .logger import logger


class RoomManager:
    """Manages rooms and enforces isolation between them."""

    ROOM_INACTIVITY_SECONDS = 20 * 60

    def __init__(self) -> None:
        self.rooms: Dict[str, GameSession] = {}
        self.player_room: Dict[str, str] = {}
        self.spectator_room: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create_room(self, room_name: str, host_id: str, game_type: str, difficulty: str) -> GameSession:
        async with self._lock:
            room_id = str(uuid.uuid4())
            session = GameSession(room_id, room_name, host_id, game_type, difficulty)
            self.rooms[room_id] = session
            self.player_room[host_id] = room_id
            logger.info('ROOM_MANAGER', f'Created room {room_id}', room_id=room_id, player_id=host_id)
            return session

    async def join_room(self, room_id: str, player_id: str) -> Optional[GameSession]:
        async with self._lock:
            session = self.rooms.get(room_id)
            if not session:
                return None
            if session.add_player(player_id):
                self.player_room[player_id] = room_id
                logger.info('ROOM_MANAGER', f'Player joined room {room_id}', room_id=room_id, player_id=player_id)
                return session
            return None

    async def spectate_room(self, room_id: str, spectator_id: str) -> Optional[GameSession]:
        async with self._lock:
            session = self.rooms.get(room_id)
            if not session:
                return None
            if session.add_spectator(spectator_id):
                self.spectator_room[spectator_id] = room_id
                logger.info('ROOM_MANAGER', f'Spectator joined room {room_id}', room_id=room_id, player_id=spectator_id)
                return session
            return None

    async def leave_room(self, room_id: str, player_id: str) -> Optional[GameSession]:
        async with self._lock:
            session = self.rooms.get(room_id)
            if not session:
                return None
            session.remove_player(player_id)
            self.player_room.pop(player_id, None)
            self.spectator_room.pop(player_id, None)
            logger.info('ROOM_MANAGER', f'Player left room {room_id}', room_id=room_id, player_id=player_id)
            if session.status == session.status.ABANDONED:
                self.rooms.pop(room_id, None)
                logger.info('ROOM_MANAGER', f'Removed abandoned room {room_id}', room_id=room_id)
            return session

    async def get_room(self, room_id: str) -> Optional[GameSession]:
        return self.rooms.get(room_id)

    async def get_room_by_player(self, player_id: str) -> Optional[GameSession]:
        room_id = self.player_room.get(player_id) or self.spectator_room.get(player_id)
        return self.rooms.get(room_id) if room_id else None

    async def list_rooms(self) -> List[Dict[str, str]]:
        return [room.get_room_summary() for room in self.rooms.values()]

    async def cleanup_inactive_rooms(self) -> None:
        now = time.time()
        expired = []
        async with self._lock:
            for room_id, session in list(self.rooms.items()):
                last_active = datetime.datetime.fromisoformat(session.last_activity.replace('Z', '+00:00')).timestamp()
                if now - last_active > self.ROOM_INACTIVITY_SECONDS or session.status == GameStatus.ABANDONED:
                    expired.append(room_id)
            for room_id in expired:
                self.rooms.pop(room_id, None)
                logger.info('ROOM_MANAGER', f'Removed inactive room {room_id}', room_id=room_id)
