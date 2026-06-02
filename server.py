#!/usr/bin/env python3
"""
Production Chess Server - WebSocket-based with modular architecture
"""

import http.server
import json
import os
import socketserver
import threading
import hashlib
import base64
import struct
import time
from typing import Dict, Set, Optional

from chess_engine import ChessBoard, Color
from game_session import SessionManager, GameStatus
from network_protocol import Protocol, MessageType
from ai_engine import Difficulty

HTTP_PORT = 3400
WS_PORT = 3401

session_manager = SessionManager()
client_sockets: Dict[str, Set] = {}  # player_id -> set of socket connections
client_lock = threading.Lock()


class HttpHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, format, *args):
        pass


class WSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        player_id = None
        current_session_id = None

        try:
            # WebSocket handshake
            raw_request = b''
            while b'\r\n\r\n' not in raw_request:
                chunk = self.request.recv(1024)
                if not chunk:
                    return
                raw_request += chunk

            request_text = raw_request.decode('utf-8', 'ignore')
            request_line, headers = self._parse_headers(request_text)

            if headers.get('upgrade', '').lower() != 'websocket':
                return

            key = headers.get('sec-websocket-key', '')
            accept = base64.b64encode(
                hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('utf-8')).digest()
            ).decode('utf-8')

            response = (
                'HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
            )
            self.request.sendall(response.encode('utf-8'))

            # Main message loop
            while True:
                message_text = self._recv_ws_message()
                if message_text is None:
                    break

                try:
                    message = json.loads(message_text)
                except (json.JSONDecodeError, ValueError):
                    continue

                msg_type = message.get('type')
                result = self._handle_message(message, player_id, current_session_id)

                if result:
                    if isinstance(result, tuple):
                        player_id, current_session_id = result
                    self._send_ws_message(json.dumps(result).encode('utf-8'))

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if player_id and current_session_id:
                session = session_manager.get_session(current_session_id)
                if session:
                    session.remove_player(player_id)

            with client_lock:
                if player_id and player_id in client_sockets:
                    client_sockets[player_id].discard(self.request)

    def _handle_message(self, message: Dict, player_id: Optional[str], session_id: Optional[str]) -> Optional[Dict]:
        """Route message to appropriate handler"""
        msg_type = message.get('type')

        handlers = {
            MessageType.CREATE_GAME.value: self._handle_create_game,
            MessageType.JOIN_GAME.value: self._handle_join_game,
            MessageType.LIST_GAMES.value: self._handle_list_games,
            MessageType.MOVE.value: self._handle_move,
            MessageType.PING.value: lambda m, p, s: Protocol.pong(),
        }

        handler = handlers.get(msg_type)
        if handler:
            return handler(message, player_id, session_id)
        return None

    def _handle_create_game(self, message: Dict, player_id: Optional[str], session_id: Optional[str]) -> Optional[tuple]:
        """Create new game session"""
        new_player_id = message.get('player_id') or f"player-{int(time.time())}"
        ai_enabled = message.get('ai_enabled', False)
        ai_difficulty = message.get('ai_difficulty', 'MEDIUM')

        new_session_id = session_manager.create_session(new_player_id, ai_enabled, ai_difficulty)
        session = session_manager.get_session(new_session_id)

        self._register_player(new_player_id)
        self._broadcast_to_session(new_session_id, Protocol.game_start(new_session_id, session.get_state()))

        return (new_player_id, new_session_id)

    def _handle_join_game(self, message: Dict, player_id: Optional[str], session_id: Optional[str]) -> Optional[tuple]:
        """Join existing game session"""
        new_player_id = message.get('player_id') or f"player-{int(time.time())}"
        join_session_id = message.get('session_id')

        if not join_session_id:
            return None

        if session_manager.join_session(join_session_id, new_player_id):
            self._register_player(new_player_id)
            session = session_manager.get_session(join_session_id)
            self._broadcast_to_session(join_session_id, Protocol.game_start(join_session_id, session.get_state()))
            return (new_player_id, join_session_id)

        return None

    def _handle_list_games(self, message: Dict, player_id: Optional[str], session_id: Optional[str]) -> Optional[Dict]:
        """List available game sessions"""
        return {
            'type': MessageType.LIST_GAMES.value,
            'games': session_manager.list_active_sessions()
        }

    def _handle_move(self, message: Dict, player_id: Optional[str], session_id: Optional[str]) -> Optional[Dict]:
        """Handle move in game"""
        if not player_id or not session_id:
            return Protocol.move_result(False, "Not in a game")

        from_row = message.get('from_row')
        from_col = message.get('from_col')
        to_row = message.get('to_row')
        to_col = message.get('to_col')
        promotion = message.get('promotion')

        if None in [from_row, from_col, to_row, to_col]:
            return Protocol.move_result(False, "Invalid move format")

        if session_manager.make_move(session_id, player_id, from_row, from_col, to_row, to_col, promotion):
            session = session_manager.get_session(session_id)

            # Get AI move if enabled
            ai_move = session.get_ai_move() if session.ai_enabled else None
            if ai_move:
                session.make_move(ai_move[0], ai_move[1], ai_move[2], ai_move[3])

            # Check game status
            if session.board.is_checkmate():
                winner_color = Color.WHITE.value if session.board.current_player == Color.BLACK else Color.BLACK.value
                self._broadcast_to_session(session_id, Protocol.checkmate(session_id, winner_color))
            elif session.board.is_stalemate():
                self._broadcast_to_session(session_id, Protocol.stalemate(session_id))
            elif session.board.is_in_check(session.board.current_player):
                self._broadcast_to_session(session_id, Protocol.check(session_id))

            # Send board update
            self._broadcast_to_session(session_id, Protocol.board_update(session_id, session.get_state()))

            return Protocol.move_result(True, ai_move=ai_move)
        else:
            return Protocol.move_result(False, "Illegal move")

    def _register_player(self, player_id: str):
        """Register player connection"""
        with client_lock:
            if player_id not in client_sockets:
                client_sockets[player_id] = set()
            client_sockets[player_id].add(self.request)

    def _broadcast_to_session(self, session_id: str, message: Dict):
        """Broadcast message to all players in session"""
        session = session_manager.get_session(session_id)
        if not session:
            return

        message_bytes = json.dumps(message).encode('utf-8')

        for player_id in session.connected_clients:
            with client_lock:
                sockets = client_sockets.get(player_id, set())
                for sock in list(sockets):
                    try:
                        self._send_ws_message_to_socket(sock, message_bytes)
                    except Exception:
                        sockets.discard(sock)

    def _send_ws_message(self, data: bytes):
        """Send WebSocket message"""
        self._send_ws_message_to_socket(self.request, data)

    @staticmethod
    def _send_ws_message_to_socket(sock, data: bytes):
        """Send WebSocket frame"""
        if isinstance(data, str):
            data = data.encode('utf-8')

        length = len(data)
        header = bytearray()
        header.append(0x81)

        if length < 126:
            header.append(length)
        elif length < 65536:
            header.append(126)
            header.extend(struct.pack('!H', length))
        else:
            header.append(127)
            header.extend(struct.pack('!Q', length))

        sock.sendall(header + data)

    @staticmethod
    def _recv_exact(sock, count: int) -> Optional[bytes]:
        """Receive exact number of bytes"""
        buffer = b''
        while len(buffer) < count:
            chunk = sock.recv(count - len(buffer))
            if not chunk:
                return None
            buffer += chunk
        return buffer

    def _recv_ws_message(self) -> Optional[str]:
        """Receive WebSocket message"""
        header = self._recv_exact(self.request, 2)
        if not header:
            return None

        b1, b2 = header
        opcode = b1 & 0x0F
        masked = b2 >> 7
        length = b2 & 0x7F

        if length == 126:
            extended = self._recv_exact(self.request, 2)
            if not extended:
                return None
            length = struct.unpack('!H', extended)[0]
        elif length == 127:
            extended = self._recv_exact(self.request, 8)
            if not extended:
                return None
            length = struct.unpack('!Q', extended)[0]

        if masked:
            mask = self._recv_exact(self.request, 4)
            if not mask:
                return None
            encoded = self._recv_exact(self.request, length)
            if not encoded:
                return None
            decoded = bytearray(length)
            for i in range(length):
                decoded[i] = encoded[i] ^ mask[i % 4]
            return decoded.decode('utf-8', 'ignore')

        data = self._recv_exact(self.request, length)
        if not data:
            return None
        return data.decode('utf-8', 'ignore')

    @staticmethod
    def _parse_headers(raw_request: str):
        """Parse HTTP headers"""
        headers = {}
        lines = raw_request.split('\r\n')
        for line in lines[1:]:
            if ': ' in line:
                name, value = line.split(': ', 1)
                headers[name.lower()] = value
        return lines[0] if lines else "", headers


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_http_server():
    """Start HTTP server for serving HTML/CSS/JS"""
    handler = HttpHandler
    server = ThreadingHTTPServer(('', HTTP_PORT), handler)
    print(f'🌐 HTTP server running on http://localhost:{HTTP_PORT}')
    server.serve_forever()


def start_ws_server():
    """Start WebSocket server for game logic"""
    server = ThreadingTCPServer(('', WS_PORT), WSHandler)
    print(f'♟️  WebSocket server running on ws://localhost:{WS_PORT}')
    server.serve_forever()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 50)
    print("  CHESS SERVER - Production Edition")
    print("=" * 50)

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    start_ws_server()
