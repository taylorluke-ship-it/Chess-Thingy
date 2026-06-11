"""
Purpose
Responsibilities
Dependencies

Provides a fallback chess AI that chooses legal moves, prioritizes captures, and seeks check or checkmate when Stockfish is unavailable.
"""

import random
from typing import Optional, Tuple

from .chess_engine import ChessGame


class FallbackAI:
    """Fallback move selector when Stockfish is unavailable."""

    PIECE_VALUE = {
        'p': 1,
        'n': 3,
        'b': 3,
        'r': 5,
        'q': 9,
        'k': 0
    }

    def choose_move(self, game: ChessGame) -> Optional[Tuple[int, int, int, int, Optional[str]]]:
        legal_moves = list(game.board.legal_moves)
        if not legal_moves:
            return None

        best_moves = []
        best_score = float('-inf')

        for move in legal_moves:
            score = self._score_move(game, move)
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        move = random.choice(best_moves)
        from_row, from_col = self._square_to_coords(move.from_square)
        to_row, to_col = self._square_to_coords(move.to_square)
        promotion = self._promotion_symbol(move)
        return from_row, from_col, to_row, to_col, promotion

    def _score_move(self, game: ChessGame, move) -> float:
        score = 0
        if game.board.is_capture(move):
            captured = game.board.piece_at(move.to_square)
            if captured:
                score += self.PIECE_VALUE.get(captured.symbol().lower(), 0) * 10
        if game.board.gives_check(move):
            score += 8
        if game.board.is_checkmate():
            score += 100
        if move.promotion:
            score += 15
        score += random.random()
        return score

    @staticmethod
    def _square_to_coords(square: int) -> Tuple[int, int]:
        file = square % 8
        rank = square // 8
        row = 7 - rank
        return row, file

    @staticmethod
    def _promotion_symbol(move) -> Optional[str]:
        if not move.promotion:
            return None
        return {
            1: 'n',
            2: 'b',
            3: 'r',
            5: 'q'
        }.get(move.promotion)
