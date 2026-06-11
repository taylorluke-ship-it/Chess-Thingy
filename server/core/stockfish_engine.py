"""
Purpose
Responsibilities
Dependencies

Integrates with the Stockfish binary for AI move selection and gracefully handles engine failures.
"""

import asyncio
import shutil
from typing import Optional, Tuple

from .error_handler import safe_stockfish_call
from .logger import logger


class StockfishEngine:
    """Stockfish wrapper that selects moves based on configured depth and skill."""

    DIFFICULTY_SETTINGS = {
        'EASY': {'skill_level': 4, 'depth': 5},
        'MEDIUM': {'skill_level': 8, 'depth': 10},
        'HARD': {'skill_level': 12, 'depth': 16},
        'EXPERT': {'skill_level': 20, 'depth': 20}
    }

    def __init__(self) -> None:
        self.binary = shutil.which('stockfish')
        self.available = self.binary is not None
        if not self.available:
            logger.error('AI_ENGINE', 'Stockfish binary not found. Fallback AI will be used.')

    async def get_best_move(
        self,
        fen: str,
        difficulty: str = 'MEDIUM'
    ) -> Optional[Tuple[int, int, int, int, Optional[str]]]:
        if not self.available:
            return None
        return await safe_stockfish_call(
            'AI_ENGINE',
            self._query_stockfish,
            fen,
            difficulty
        )

    async def _query_stockfish(self, fen: str, difficulty: str) -> Optional[Tuple[int, int, int, int, Optional[str]]]:
        settings = self.DIFFICULTY_SETTINGS.get(difficulty.upper(), self.DIFFICULTY_SETTINGS['MEDIUM'])
        try:
            process = await asyncio.create_subprocess_exec(
                self.binary,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            commands = [
                'uci',
                f'setoption name Skill Level value {settings["skill_level"]}',
                f'setoption name Threads value 1',
                f'setoption name MultiPV value 1',
                f'position fen {fen}',
                f'go depth {settings["depth"]}',
                'quit'
            ]
            stdin = '\n'.join(commands) + '\n'
            stdout, stderr = await process.communicate(stdin.encode('utf-8'))
            if stderr:
                logger.error('AI_ENGINE', 'Stockfish stderr', extra={'stderr': stderr.decode('utf-8', errors='ignore')})
            output = stdout.decode('utf-8', errors='ignore')
            move_line = next((line for line in output.splitlines() if line.startswith('bestmove ')), None)
            if not move_line:
                return None
            parts = move_line.split()
            if len(parts) < 2:
                return None
            uci_move = parts[1]
            return self._uci_to_coords(uci_move)
        except Exception as exc:
            logger.error('AI_ENGINE', f'Stockfish query failed: {exc}', extra={'exception': repr(exc)})
            return None

    @staticmethod
    def _uci_to_coords(uci: str) -> Optional[Tuple[int, int, int, int, Optional[str]]]:
        if len(uci) < 4:
            return None
        from_col = ord(uci[0]) - ord('a')
        from_row = 8 - int(uci[1])
        to_col = ord(uci[2]) - ord('a')
        to_row = 8 - int(uci[3])
        promotion = uci[4] if len(uci) == 5 else None
        return from_row, from_col, to_row, to_col, promotion
