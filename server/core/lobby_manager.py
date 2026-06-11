"""
Purpose
Responsibilities
Dependencies

Exposes lobby information and room browsing features to the WebSocket server.
"""

from typing import Dict, List, Optional

from .room_manager import RoomManager


class LobbyManager:
    """Central lobby view for available rooms."""

    def __init__(self, room_manager: RoomManager) -> None:
        self.room_manager = room_manager

    async def list_rooms(self) -> List[Dict[str, str]]:
        rooms = await self.room_manager.list_rooms()
        return rooms

    async def find_room(self, room_id: str) -> Optional[Dict[str, str]]:
        room = await self.room_manager.get_room(room_id)
        return room.get_room_summary() if room else None
