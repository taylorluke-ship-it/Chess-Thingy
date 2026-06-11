"""
Purpose
Responsibilities
Dependencies

Provides protective execution wrappers to prevent subsystem failures from crashing the server.
"""

import asyncio
import json
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from .logger import logger


class ErrorContext:
    """Context metadata for safe execution logging."""

    def __init__(
        self,
        subsystem: str,
        room_id: Optional[str] = None,
        player_id: Optional[str] = None,
        action: Optional[str] = None
    ) -> None:
        self.subsystem = subsystem
        self.room_id = room_id
        self.player_id = player_id
        self.action = action or 'Unknown'


def safe_execute(
    subsystem: str,
    func: Callable[..., Any],
    *args: Any,
    room_id: Optional[str] = None,
    player_id: Optional[str] = None,
    action: str = 'Execute',
    **kwargs: Any
) -> Any:
    """Execute a synchronous function safely and continue on error."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.error(
            subsystem,
            f"{action} failed: {exc}",
            room_id=room_id,
            player_id=player_id,
            extra={'exception': repr(exc)}
        )
        return None


async def safe_async_execute(
    subsystem: str,
    func: Callable[..., Any],
    *args: Any,
    room_id: Optional[str] = None,
    player_id: Optional[str] = None,
    action: str = 'AsyncExecute',
    **kwargs: Any
) -> Any:
    """Execute an async function safely and continue on error."""
    try:
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    except Exception as exc:
        logger.error(
            subsystem,
            f"{action} failed: {exc}",
            room_id=room_id,
            player_id=player_id,
            extra={'exception': repr(exc)}
        )
        return None


def safe_broadcast(
    subsystem: str,
    targets: list,
    payload: Dict[str, Any],
    room_id: Optional[str] = None,
    player_id: Optional[str] = None,
    action: str = 'Broadcast'
) -> None:
    """Broadcast a payload safely across multiple websocket targets."""
    serialized = payload
    if isinstance(payload, dict):
        try:
            serialized = json.dumps(payload)
        except Exception:
            serialized = str(payload)

    for target in list(targets):
        try:
            if hasattr(target, 'send'):
                maybe_coro = target.send(serialized)
                if asyncio.iscoroutine(maybe_coro):
                    asyncio.create_task(maybe_coro)
        except Exception as exc:
            logger.error(
                subsystem,
                f"{action} failed for connection: {exc}",
                room_id=room_id,
                player_id=player_id,
                extra={'exception': repr(exc)}
            )


def safe_database_query(
    subsystem: str,
    query_func: Callable[..., Any],
    *args: Any,
    room_id: Optional[str] = None,
    player_id: Optional[str] = None,
    action: str = 'DatabaseQuery',
    **kwargs: Any
) -> Any:
    """Execute a database query safely without crashing the application."""
    try:
        return query_func(*args, **kwargs)
    except Exception as exc:
        logger.error(
            subsystem,
            f"{action} failed: {exc}",
            room_id=room_id,
            player_id=player_id,
            extra={'exception': repr(exc)}
        )
        return None


def safe_stockfish_call(
    subsystem: str,
    query_func: Callable[..., Any],
    *args: Any,
    room_id: Optional[str] = None,
    player_id: Optional[str] = None,
    action: str = 'StockfishCall',
    **kwargs: Any
) -> Any:
    """Execute a stockfish call safely and fall back if needed."""
    try:
        return query_func(*args, **kwargs)
    except Exception as exc:
        logger.error(
            subsystem,
            f"{action} failed: {exc}",
            room_id=room_id,
            player_id=player_id,
            extra={'exception': repr(exc)}
        )
        return None
