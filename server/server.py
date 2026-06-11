"""
Purpose
Responsibilities
Dependencies

Runs the production-grade chess server with HTTP static hosting and asyncio WebSocket multiplayer support.
Implements "zombie architecture" - no subsystem failure crashes the server.
"""

import asyncio
import http.server
import json
import os
import socketserver
import threading
from functools import partial
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets import WebSocketServerProtocol

from server.core.error_handler import safe_async_execute, safe_broadcast
from server.core.lobby_manager import LobbyManager
from server.core.logger import logger
from server.core.persistence import PersistenceManager
from server.core.protocol import MessageType, Protocol
from server.core.room_manager import RoomManager
from server.core.stockfish_engine import StockfishEngine
from server.core.fallback_ai import FallbackAI


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTP server that handles requests in separate threads."""
    daemon_threads = True
    allow_reuse_address = True


class ChessServer:
    """Main server orchestration class for room lifecycle and message routing."""

    def __init__(self, host: str = '0.0.0.0', http_port: int = 8000, ws_port: int = 8765) -> None:
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client'))
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
        self.room_manager = RoomManager()
        self.lobby_manager = LobbyManager(self.room_manager)
        self.persistence = PersistenceManager(self.data_dir)
        self.stockfish = StockfishEngine()
        self.fallback_ai = FallbackAI()
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        self.connection_info: Dict[WebSocketServerProtocol, Dict[str, Optional[str]]] = {}
        self._connection_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start HTTP and WebSocket servers."""
        logger.info('SERVER', f'Starting HTTP server on port {self.http_port}')
        threading.Thread(target=self._start_http_server, daemon=True).start()

        logger.info('SERVER', f'Starting WebSocket server on port {self.ws_port}')
        try:
            async with websockets.serve(self._ws_handler, self.host, self.ws_port, ping_interval=20, ping_timeout=10):
                await self._background_tasks()
        except Exception as exc:
            logger.error('SERVER', f'WebSocket server error: {exc}')

    def _start_http_server(self) -> None:
        """Start HTTP server for serving static files."""
        try:
            handler = partial(http.server.SimpleHTTPRequestHandler, directory=self.client_dir)
            server = ThreadingHTTPServer((self.host, self.http_port), handler)
            logger.info('SERVER', f'HTTP server serving {self.client_dir}')
            server.serve_forever()
        except Exception as exc:
            logger.error('SERVER', f'HTTP server error: {exc}')

    async def _background_tasks(self) -> None:
        """Run background maintenance tasks continuously."""
        while True:
            try:
                await self.room_manager.cleanup_inactive_rooms()
                await self.persistence.sync_cached_queries()
            except Exception as exc:
                logger.error('SERVER', f'Background task failure: {exc}')
            await asyncio.sleep(60)

    async def _ws_handler(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle WebSocket connections."""
        self.connection_info[websocket] = {'player_id': None, 'room_id': None}
        logger.info('SERVER', f'WebSocket client connected: {websocket.remote_address}')
        try:
            async for raw_message in websocket:
                await self._handle_raw_message(websocket, raw_message)
        except websockets.ConnectionClosed:
            pass
        except Exception as exc:
            logger.error('SERVER', f'WebSocket handler error: {exc}')
        finally:
            await self._cleanup_connection(websocket)

    async def _handle_raw_message(self, websocket: WebSocketServerProtocol, raw_message: str) -> None:
        """Parse and validate incoming message."""
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(websocket, 'Malformed JSON packet')
            return

        message, error = Protocol.validate_message(payload)
        if error:
            await self._send_error(websocket, error)
            return

        await self._route_message(websocket, message)

    async def _route_message(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Route message to appropriate handler."""
        try:
            message_type = message['type']
            if message_type == MessageType.CREATE_ROOM.value:
                await self._handle_create_room(websocket, message)
            elif message_type == MessageType.JOIN_ROOM.value:
                await self._handle_join_room(websocket, message)
            elif message_type == MessageType.LEAVE_ROOM.value:
                await self._handle_leave_room(websocket, message)
            elif message_type == MessageType.REFRESH_ROOMS.value:
                await self._handle_refresh_rooms(websocket)
            elif message_type == MessageType.START_GAME.value:
                await self._handle_start_game(websocket, message)
            elif message_type == MessageType.MOVE.value:
                await self._handle_move(websocket, message)
            elif message_type == MessageType.CHAT.value:
                await self._handle_chat(websocket, message)
            elif message_type == MessageType.HEARTBEAT.value:
                await self._send_message(websocket, Protocol.pong())
            else:
                await self._send_error(websocket, f'Unsupported message type: {message_type}')
        except Exception as exc:
            logger.error('SERVER', f'Message routing error: {exc}')
            await self._send_error(websocket, 'Internal server error')

    async def _send_message(self, websocket: WebSocketServerProtocol, payload: Dict[str, Any]) -> None:
        """Send message to client without crashing if it fails."""
        try:
            await websocket.send(json.dumps(payload))
        except Exception as exc:
            logger.error('SERVER', f'Failed to send message: {exc}')

    async def _send_error(self, websocket: WebSocketServerProtocol, message: str, code: Optional[str] = None) -> None:
        """Send error message to client."""
        await self._send_message(websocket, Protocol.error(message, code))

    async def _broadcast_room(self, room_id: str, payload: Dict[str, Any]) -> None:
        """Broadcast message to all players in a room."""
        targets: List[WebSocketServerProtocol] = []
        async with self._connection_lock:
            for connection, info in self.connection_info.items():
                if info.get('room_id') == room_id:
                    targets.append(connection)
        safe_broadcast('SERVER', targets, payload, room_id=room_id)

    async def _handle_create_room(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Create new room and notify client."""
        try:
            player_id = message['player_id']
            room_name = message['room_name']
            game_type = message['game_type']
            difficulty = message.get('difficulty', 'MEDIUM')
            session = await self.room_manager.create_room(room_name, player_id, game_type, difficulty)
            await self._register_participant(websocket, player_id, session.room_id)
            await self.persistence.save_room(session.serialize())
            await self._send_message(websocket, Protocol.board_update(session.room_id, session.serialize()))
            logger.info('SERVER', 'Room created', room_id=session.room_id, player_id=player_id)
        except Exception as exc:
            logger.error('SERVER', f'Create room failed: {exc}')
            await self._send_error(websocket, 'Failed to create room')

    async def _handle_join_room(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Join existing room or spectate."""
        try:
            player_id = message['player_id']
            room_id = message['room_id']
            session = await self.room_manager.join_room(room_id, player_id)
            if session:
                await self._register_participant(websocket, player_id, room_id)
                await self.persistence.save_room(session.serialize())
                await self._broadcast_room(room_id, Protocol.player_joined(room_id, player_id))
                await self._broadcast_room(room_id, Protocol.board_update(room_id, session.serialize()))
                logger.info('SERVER', 'Player joined room', room_id=room_id, player_id=player_id)
                return
            session = await self.room_manager.spectate_room(room_id, player_id)
            if session:
                await self._register_participant(websocket, player_id, room_id)
                await self.persistence.save_room(session.serialize())
                await self._send_message(websocket, Protocol.spectator_joined(room_id, player_id))
                await self._send_message(websocket, Protocol.board_update(room_id, session.serialize()))
                logger.info('SERVER', 'Spectator joined room', room_id=room_id, player_id=player_id)
                return
            await self._send_error(websocket, 'Unable to join or spectate room')
        except Exception as exc:
            logger.error('SERVER', f'Join room failed: {exc}')
            await self._send_error(websocket, 'Failed to join room')

    async def _handle_leave_room(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Remove player from room."""
        try:
            player_id = message['player_id']
            room_id = message['room_id']
            session = await self.room_manager.leave_room(room_id, player_id)
            await self._unregister_participant(websocket)
            if session:
                await self.persistence.save_room(session.serialize())
                await self._broadcast_room(room_id, Protocol.player_left(room_id, player_id))
                logger.info('SERVER', 'Player left room', room_id=room_id, player_id=player_id)
                return
            await self._send_error(websocket, 'Room not found during leave')
        except Exception as exc:
            logger.error('SERVER', f'Leave room failed: {exc}')
            await self._send_error(websocket, 'Failed to leave room')

    async def _handle_refresh_rooms(self, websocket: WebSocketServerProtocol) -> None:
        """Send list of available rooms."""
        try:
            rooms = await self.lobby_manager.list_rooms()
            await self._send_message(websocket, {
                'type': MessageType.REFRESH_ROOMS.value,
                'rooms': rooms
            })
        except Exception as exc:
            logger.error('SERVER', f'Refresh rooms failed: {exc}')
            await self._send_error(websocket, 'Failed to refresh rooms')

    async def _handle_start_game(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Start game in room."""
        try:
            player_id = message['player_id']
            room_id = message['room_id']
            session = await self.room_manager.get_room(room_id)
            if not session:
                await self._send_error(websocket, 'Room not found')
                return
            if session.host_id != player_id:
                await self._send_error(websocket, 'Only the host can start the game')
                return
            if session.game_type == 'ai' or len(session.players) == 2:
                session.status = session.status.IN_PROGRESS
                session.touch()
                await self.persistence.save_room(session.serialize())
                await self._broadcast_room(room_id, Protocol.board_update(room_id, session.serialize()))
                logger.info('SERVER', 'Game started', room_id=room_id)
                return
            await self._send_error(websocket, 'Room needs two players or AI enabled to start')
        except Exception as exc:
            logger.error('SERVER', f'Start game failed: {exc}')
            await self._send_error(websocket, 'Failed to start game')

    async def _handle_move(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Process player move and AI move if applicable."""
        try:
            player_id = message['player_id']
            room_id = message['room_id']
            session = await self.room_manager.get_room(room_id)
            if not session:
                await self._send_error(websocket, 'Room not found')
                return
            success, error = await session.make_move(
                player_id,
                int(message['from_row']),
                int(message['from_col']),
                int(message['to_row']),
                int(message['to_col']),
                message.get('promotion')
            )
            if not success:
                await self._send_error(websocket, error or 'Move rejected')
                return
            try:
                if session.move_history:
                    await self.persistence.save_move(
                        room_id,
                        player_id,
                        session.move_history[-1]['uci'],
                        session.move_history[-1]
                    )
            except Exception as exc:
                logger.error('SERVER', f'Move persistence failed: {exc}', room_id=room_id, player_id=player_id)
            await self.persistence.save_room(session.serialize())
            await self._broadcast_room(room_id, Protocol.board_update(room_id, session.serialize()))
            if session.status in (session.status.CHECKMATE, session.status.STALEMATE, session.status.DRAW):
                await self._broadcast_room(room_id, Protocol.game_over(room_id, session.status.value))
                try:
                    await self.persistence.save_game(session.serialize())
                except Exception as exc:
                    logger.error('SERVER', f'Game persistence failed: {exc}', room_id=room_id)
                return
            if session.ai_enabled and session.board.board.turn == False:
                try:
                    ai_move = await session.request_ai_move(self.stockfish, self.fallback_ai)
                    if ai_move:
                        try:
                            uci_move = f"{chr(97 + ai_move['from_col'])}{8 - ai_move['from_row']}{chr(97 + ai_move['to_col'])}{8 - ai_move['to_row']}"
                            if ai_move.get('promotion'):
                                uci_move += ai_move['promotion']
                            await self.persistence.save_move(room_id, session.host_id, uci_move, ai_move)
                        except Exception as exc:
                            logger.error('SERVER', f'AI move persistence failed: {exc}', room_id=room_id)
                        await self.persistence.save_room(session.serialize())
                        await self._broadcast_room(room_id, Protocol.board_update(room_id, session.serialize()))
                        if session.status in (session.status.CHECKMATE, session.status.STALEMATE, session.status.DRAW):
                            await self._broadcast_room(room_id, Protocol.game_over(room_id, session.status.value))
                            try:
                                await self.persistence.save_game(session.serialize())
                            except Exception as exc:
                                logger.error('SERVER', f'Game end persistence failed: {exc}', room_id=room_id)
                except Exception as exc:
                    logger.error('AI_ENGINE', f'AI move request failed: {exc}', room_id=room_id)
        except Exception as exc:
            logger.error('SERVER', f'Move handler error: {exc}')
            await self._send_error(websocket, 'Move processing failed')

    async def _handle_chat(self, websocket: WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Handle chat message."""
        try:
            player_id = message['player_id']
            room_id = message['room_id']
            session = await self.room_manager.get_room(room_id)
            if not session:
                await self._send_error(websocket, 'Room not found')
                return
            session.add_chat_message(player_id, message['message'])
            try:
                await self.persistence.save_room(session.serialize())
            except Exception as exc:
                logger.error('SERVER', f'Chat persistence failed: {exc}', room_id=room_id)
            await self._broadcast_room(room_id, Protocol.chat(room_id, player_id, message['message']))
        except Exception as exc:
            logger.error('SERVER', f'Chat handler error: {exc}')

    async def _register_participant(self, websocket: WebSocketServerProtocol, player_id: str, room_id: str) -> None:
        """Register player connection in tracking structures."""
        try:
            async with self._connection_lock:
                self.connections[player_id] = websocket
                self.connection_info[websocket] = {'player_id': player_id, 'room_id': room_id}
        except Exception as exc:
            logger.error('SERVER', f'Participant registration failed: {exc}', player_id=player_id)

    async def _unregister_participant(self, websocket: WebSocketServerProtocol) -> None:
        """Unregister player connection."""
        try:
            async with self._connection_lock:
                info = self.connection_info.get(websocket, {})
                player_id = info.get('player_id')
                if player_id and self.connections.get(player_id) == websocket:
                    self.connections.pop(player_id, None)
                self.connection_info.pop(websocket, None)
        except Exception as exc:
            logger.error('SERVER', f'Participant unregistration failed: {exc}')

    async def _cleanup_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Clean up disconnected player."""
        try:
            info = self.connection_info.get(websocket, {})
            player_id = info.get('player_id')
            room_id = info.get('room_id')
            await self._unregister_participant(websocket)
            if player_id and room_id:
                session = await self.room_manager.get_room(room_id)
                if session:
                    session.remove_player(player_id)
                    try:
                        await self.persistence.save_disconnect(room_id, player_id)
                        await self.persistence.save_room(session.serialize())
                    except Exception as exc:
                        logger.error('SERVER', f'Disconnect persistence failed: {exc}', room_id=room_id, player_id=player_id)
                    await self._broadcast_room(room_id, Protocol.player_left(room_id, player_id))
                    logger.info('SERVER', 'Player disconnected', room_id=room_id, player_id=player_id)
        except Exception as exc:
            logger.error('SERVER', f'Connection cleanup failed: {exc}')


if __name__ == '__main__':
    server = ChessServer()
    asyncio.run(server.start())
