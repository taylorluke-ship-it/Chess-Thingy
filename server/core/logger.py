"""
Purpose
Responsibilities
Dependencies

Provides timestamped file logging for all subsystems and gracefully handles file I/O failures.
"""

import datetime
import json
import os
import threading
from typing import Any, Dict, Optional


class Logger:
    """Centralized logger for subsystems and error tracking."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.log_dir = os.path.join(data_dir, 'logs')
        self._lock = threading.Lock()
        os.makedirs(self.log_dir, exist_ok=True)
        self._files = {
            'server': os.path.join(self.log_dir, 'server.log'),
            'errors': os.path.join(self.log_dir, 'errors.log'),
            'games': os.path.join(self.log_dir, 'games.log'),
            'ai': os.path.join(self.log_dir, 'ai.log')
        }

    def _format_record(
        self,
        subsystem: str,
        message: str,
        severity: str = 'INFO',
        room_id: Optional[str] = None,
        player_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> str:
        timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
        record = {
            'timestamp': timestamp,
            'subsystem': subsystem,
            'severity': severity,
            'room_id': room_id,
            'player_id': player_id,
            'message': message,
            'extra': extra or {}
        }
        return json.dumps(record, ensure_ascii=False)

    def _write(self, file_path: str, text: str) -> None:
        try:
            with self._lock, open(file_path, 'a', encoding='utf-8') as handle:
                handle.write(text + '\n')
        except Exception:
            # If logging fails, fallback to the console but do not raise.
            print(f"Logging failure writing to {file_path}: {text}")

    def log(
        self,
        subsystem: str,
        message: str,
        severity: str = 'INFO',
        room_id: Optional[str] = None,
        player_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        entry = self._format_record(subsystem, message, severity, room_id, player_id, extra)
        file_path = self._files.get(subsystem.lower(), self._files['server'])
        self._write(file_path, entry)

    def error(
        self,
        subsystem: str,
        message: str,
        room_id: Optional[str] = None,
        player_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        self.log(subsystem, message, severity='ERROR', room_id=room_id, player_id=player_id, extra=extra)

    def info(
        self,
        subsystem: str,
        message: str,
        room_id: Optional[str] = None,
        player_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        self.log(subsystem, message, severity='INFO', room_id=room_id, player_id=player_id, extra=extra)


logger = Logger(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data'))
