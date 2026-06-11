"""
Purpose
Responsibilities
Dependencies

Wraps python-chess for legal move generation, board state management, FEN serialization, and PGN history.
"""

import chess
import chess.pgn
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _to_square_name(row: int, col: int) -> str:
    file = 'abcdefgh'[col]
    rank = str(8 - row)
    return f'{file}{rank}'


def _from_square_name(square: str) -> Tuple[int, int]:
    file = ord(square[0]) - ord('a')
    rank = int(square[1])
    row = 8 - rank
    return row, file


class ChessGame:
    """Encapsulates a python-chess board and exposes safe move operations."""

    def __init__(self, fen: Optional[str] = None) -> None:
        self.board = chess.Board(fen) if fen else chess.Board()
        self.pgn_game = chess.pgn.Game()
        self.pgn_node = self.pgn_game
        self.history: List[Dict[str, Any]] = []

    def get_state(self) -> Dict[str, Any]:
        return {
            'fen': self.board.fen(),
            'current_player': 'white' if self.board.turn == chess.WHITE else 'black',
            'fullmove_number': self.board.fullmove_number,
            'halfmove_clock': self.board.halfmove_clock,
            'is_check': self.board.is_check(),
            'is_checkmate': self.board.is_checkmate(),
            'is_stalemate': self.board.is_stalemate(),
            'is_insufficient_material': self.board.is_insufficient_material(),
            'is_seventyfive_moves': self.board.is_seventyfive_moves(),
            'is_fivefold_repetition': self.board.is_fivefold_repetition(),
            'move_history': list(self.history),
            'pieces': self._serialize_pieces(),
            'legal_moves': self._serialize_legal_moves()
        }

    def _serialize_pieces(self) -> List[Dict[str, Any]]:
        pieces = []
        for square, piece in self.board.piece_map().items():
            row, col = _from_square_name(chess.square_name(square))
            pieces.append({
                'type': piece.symbol().lower(),
                'color': 'white' if piece.color == chess.WHITE else 'black',
                'row': row,
                'col': col
            })
        return pieces

    def _serialize_legal_moves(self) -> List[Dict[str, Any]]:
        moves = []
        for move in self.board.legal_moves:
            from_row, from_col = _from_square_name(chess.square_name(move.from_square))
            to_row, to_col = _from_square_name(chess.square_name(move.to_square))
            moves.append({
                'from_row': from_row,
                'from_col': from_col,
                'to_row': to_row,
                'to_col': to_col,
                'promotion': move.promotion and chess.piece_symbol(move.promotion).lower()
            })
        return moves

    def get_legal_moves_for_square(self, row: int, col: int) -> List[Dict[str, int]]:
        square = chess.parse_square(_to_square_name(row, col))
        if self.board.piece_at(square) is None or self.board.piece_at(square).color != self.board.turn:
            return []
        moves = []
        for move in self.board.legal_moves:
            if move.from_square == square:
                to_row, to_col = _from_square_name(chess.square_name(move.to_square))
                moves.append({'row': to_row, 'col': to_col, 'promotion': move.promotion})
        return moves

    def apply_move(
        self,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
        promotion: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        if self.board.is_game_over():
            return False, 'Game has already ended'

        from_square = chess.parse_square(_to_square_name(from_row, from_col))
        to_square = chess.parse_square(_to_square_name(to_row, to_col))
        promotion_piece = None
        if promotion:
            promotion_piece = {
                'q': chess.QUEEN,
                'r': chess.ROOK,
                'b': chess.BISHOP,
                'n': chess.KNIGHT
            }.get(promotion.lower())

        move = chess.Move(from_square, to_square, promotion=promotion_piece)
        if move not in self.board.legal_moves:
            return False, 'Illegal move'

        self.board.push(move)
        self._append_move_to_history(move)
        return True, None

    def _append_move_to_history(self, move: chess.Move) -> None:
        san = self.board.peek().san() if self.board.move_stack else self.board.san(move)
        self.history.append({
            'uci': move.uci(),
            'san': san,
            'from': _from_square_name(chess.square_name(move.from_square)),
            'to': _from_square_name(chess.square_name(move.to_square)),
            'promotion': move.promotion and chess.piece_name(move.promotion).lower(),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        self.pgn_node = self.pgn_node.add_variation(move)

    def get_result(self) -> Optional[str]:
        if self.board.is_checkmate():
            return 'checkmate'
        if self.board.is_stalemate():
            return 'stalemate'
        if self.board.is_insufficient_material():
            return 'insufficient_material'
        if self.board.is_seventyfive_moves():
            return 'seventyfive_moves'
        if self.board.is_fivefold_repetition():
            return 'fivefold_repetition'
        return None

    def is_check(self) -> bool:
        return self.board.is_check()

    def get_pgn(self) -> str:
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=False)
        return self.pgn_game.accept(exporter)
