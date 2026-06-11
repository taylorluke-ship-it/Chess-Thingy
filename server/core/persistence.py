"""
Purpose
Responsibilities
Dependencies

Implements SQLite persistence with fallback in-memory caching and safe retry behavior.
"""

import asyncio
import datetime
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from .error_handler import safe_database_query
from .logger import logger


class PersistenceManager:
    """Manages database persistence for rooms, games, moves, and statistics."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.db_path = os.path.join(self.data_dir, 'database.db')
        os.makedirs(self.data_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: List[Dict[str, Any]] = []
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        try:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.execute('PRAGMA journal_mode=WAL')
            self._connection.execute('PRAGMA foreign_keys=ON')
            self._create_tables()
            logger.info('DATABASE', 'SQLite database initialized', extra={'path': self.db_path})
        except Exception as exc:
            logger.error('DATABASE', f'Failed to initialize database: {exc}', extra={'exception': repr(exc)})
            self._connection = None

    def _create_tables(self) -> None:
        if not self._connection:
            return
        cursor = self._connection.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                player_id TEXT PRIMARY KEY,
                display_name TEXT
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                room_name TEXT,
                host_id TEXT,
                game_type TEXT,
                difficulty TEXT,
                status TEXT,
                updated_at TEXT,
                payload TEXT
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                room_id TEXT,
                result TEXT,
                winner TEXT,
                payload TEXT,
                updated_at TEXT,
                FOREIGN KEY(room_id) REFERENCES rooms(room_id)
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS moves (
                move_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT,
                player_id TEXT,
                uci TEXT,
                metadata TEXT,
                created_at TEXT,
                FOREIGN KEY(room_id) REFERENCES rooms(room_id)
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS statistics (
                player_id TEXT PRIMARY KEY,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0
            )
            '''
        )
        self._connection.commit()

    def _execute_sync(self, sql: str, params: tuple = ()) -> List[tuple]:
        if not self._connection:
            raise RuntimeError('Database connection unavailable')
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            self._connection.commit()
            return rows

    async def _run_query(self, sql: str, params: tuple = ()) -> Optional[List[tuple]]:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._execute_sync, sql, params)
        except Exception:
            self._cache.append({'sql': sql, 'params': params})
            logger.error('DATABASE', f'Falling back to in-memory cache for query', extra={'sql': sql, 'params': params})
            return None

    async def sync_cached_queries(self) -> None:
        if not self._connection or not self._cache:
            return
        with self._lock:
            while self._cache:
                item = self._cache.pop(0)
                try:
                    self._connection.execute(item['sql'], item['params'])
                except Exception as exc:
                    logger.error('DATABASE', f'Cached query failed: {exc}', extra={'item': item})
                    self._cache.insert(0, item)
                    break
            self._connection.commit()

    async def save_room(self, room_state: Dict[str, Any]) -> None:
        await safe_database_query(
            'DATABASE',
            self._run_query,
            '''
            INSERT INTO rooms (room_id, room_name, host_id, game_type, difficulty, status, updated_at, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                room_name=excluded.room_name,
                host_id=excluded.host_id,
                game_type=excluded.game_type,
                difficulty=excluded.difficulty,
                status=excluded.status,
                updated_at=excluded.updated_at,
                payload=excluded.payload
            ''',
            (
                room_state['room_id'],
                room_state['room_name'],
                room_state['host_id'],
                room_state['game_type'],
                room_state['difficulty'],
                room_state['status'],
                room_state['updated_at'],
                json.dumps(room_state)
            ),
            room_id=room_state.get('room_id')
        )

    async def save_game(self, game_state: Dict[str, Any]) -> None:
        await safe_database_query(
            'DATABASE',
            self._run_query,
            '''
            INSERT OR REPLACE INTO games (game_id, room_id, result, winner, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                game_state['room_id'],
                game_state['room_id'],
                game_state.get('result', 'unknown'),
                game_state.get('winner'),
                json.dumps(game_state),
                game_state['updated_at']
            ),
            room_id=game_state.get('room_id')
        )

    async def save_move(self, room_id: str, player_id: str, uci: str, metadata: Dict[str, Any]) -> None:
        await safe_database_query(
            'DATABASE',
            self._run_query,
            '''
            INSERT INTO moves (room_id, player_id, uci, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                room_id,
                player_id,
                uci,
                json.dumps(metadata),
                metadata.get('created_at') or datetime.datetime.utcnow().isoformat() + 'Z'
            ),
            room_id=room_id,
            player_id=player_id
        )

    async def save_disconnect(self, room_id: str, player_id: str) -> None:
        await safe_database_query(
            'DATABASE',
            self._run_query,
            '''
            INSERT OR IGNORE INTO statistics (player_id, games_played, wins, losses, draws)
            VALUES (?, 0, 0, 0, 0)
            ''',
            (player_id,),
            room_id=room_id,
            player_id=player_id
        )

    async def list_rooms(self) -> List[Dict[str, Any]]:
        rows = await self._run_query('SELECT payload FROM rooms', ())
        if not rows:
            return []
        rooms = []
        for row in rows:
            try:
                rooms.append(json.loads(row[0]))
            except Exception:
                continue
        return rooms
