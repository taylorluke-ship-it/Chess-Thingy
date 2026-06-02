"""
AI Engine - Minimax with alpha-beta pruning and difficulty levels
"""

import random
from typing import Tuple, Optional
from enum import Enum
from chess_engine import ChessBoard, Color, PieceType


class Difficulty(Enum):
    EASY = 1
    MEDIUM = 3
    HARD = 5


class AIEngine:
    def __init__(self, difficulty: Difficulty = Difficulty.MEDIUM):
        self.difficulty = difficulty
        self.max_depth = difficulty.value
        self.transposition_table = {}

    def reset_cache(self):
        self.transposition_table = {}

    def get_best_move(self, board: ChessBoard) -> Optional[Tuple[int, int, int, int]]:
        """Returns best move as (from_row, from_col, to_row, to_col)"""
        self.reset_cache()
        best_move = None
        best_score = float('-inf')

        # Get all possible moves
        color = board.current_player
        legal_moves = self._get_all_legal_moves(board, color)

        if not legal_moves:
            return None

        # Add randomness at easy difficulty
        if self.difficulty == Difficulty.EASY:
            return random.choice(legal_moves) if legal_moves else None

        # Minimax search
        for move in legal_moves:
            board_copy = self._copy_board(board)
            board_copy.make_move(move[0], move[1], move[2], move[3])
            score = self._minimax(board_copy, self.max_depth - 1, float('-inf'), float('inf'), False)

            if score > best_score:
                best_score = score
                best_move = move

        return best_move

    def _minimax(self, board: ChessBoard, depth: int, alpha: float, beta: float, is_maximizing: bool) -> float:
        """Minimax with alpha-beta pruning"""
        # Transposition table lookup
        fen = board.get_fen()
        if fen in self.transposition_table:
            return self.transposition_table[fen][depth] if depth in self.transposition_table[fen] else None

        # Terminal node
        if depth == 0 or board.is_checkmate() or board.is_stalemate():
            score = self._evaluate_position(board)
            if fen not in self.transposition_table:
                self.transposition_table[fen] = {}
            self.transposition_table[fen][depth] = score
            return score

        legal_moves = self._get_all_legal_moves(board, board.current_player)

        if not legal_moves:
            score = float('-inf') if board.is_checkmate() else 0
            return score

        if is_maximizing:
            max_eval = float('-inf')
            for move in legal_moves:
                board_copy = self._copy_board(board)
                board_copy.make_move(move[0], move[1], move[2], move[3])
                eval_score = self._minimax(board_copy, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in legal_moves:
                board_copy = self._copy_board(board)
                board_copy.make_move(move[0], move[1], move[2], move[3])
                eval_score = self._minimax(board_copy, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def _evaluate_position(self, board: ChessBoard) -> float:
        """Evaluate board position"""
        if board.is_checkmate():
            return float('inf') if board.current_player == Color.BLACK else float('-inf')
        if board.is_stalemate():
            return 0

        piece_values = {
            PieceType.PAWN: 1,
            PieceType.KNIGHT: 3,
            PieceType.BISHOP: 3.3,
            PieceType.ROOK: 5,
            PieceType.QUEEN: 9,
            PieceType.KING: 0
        }

        score = 0
        for piece, row, col in board.get_all_pieces(Color.WHITE):
            score += piece_values.get(piece.type, 0)
            score += self._get_position_bonus(piece, row, col, Color.WHITE)

        for piece, row, col in board.get_all_pieces(Color.BLACK):
            score -= piece_values.get(piece.type, 0)
            score -= self._get_position_bonus(piece, row, col, Color.BLACK)

        # Mobility bonus
        white_moves = sum(len(board.get_legal_moves(r, c)) for _, r, c in board.get_all_pieces(Color.WHITE))
        black_moves = sum(len(board.get_legal_moves(r, c)) for _, r, c in board.get_all_pieces(Color.BLACK))
        score += (white_moves - black_moves) * 0.1

        # Check bonus
        if board.is_in_check(Color.BLACK):
            score += 0.5
        if board.is_in_check(Color.WHITE):
            score -= 0.5

        return score

    def _get_position_bonus(self, piece, row: int, col: int, color: Color) -> float:
        """Positional evaluation bonuses"""
        bonus = 0

        # Pawn structure
        if piece.type == PieceType.PAWN:
            if color == Color.WHITE:
                bonus += (7 - row) * 0.1  # Encourage advancement
            else:
                bonus += row * 0.1

        # Center control
        center_distance = abs(row - 3.5) + abs(col - 3.5)
        bonus += (7 - center_distance) * 0.05

        return bonus

    def _get_all_legal_moves(self, board: ChessBoard, color: Color) -> list:
        """Get all legal moves for a color"""
        moves = []
        for piece, row, col in board.get_all_pieces(color):
            for to_row, to_col in board.get_legal_moves(row, col):
                moves.append((row, col, to_row, to_col))
        return moves

    def _copy_board(self, board: ChessBoard) -> ChessBoard:
        """Deep copy a board"""
        new_board = ChessBoard.__new__(ChessBoard)
        new_board.board = [[board.get_piece(r, c) for c in range(8)] for r in range(8)]
        
        # Deep copy pieces
        for r in range(8):
            for c in range(8):
                piece = new_board.board[r][c]
                if piece:
                    new_board.board[r][c] = Piece(piece.type, piece.color)
                    new_board.board[r][c].moved = piece.moved

        new_board.white_king_pos = board.white_king_pos
        new_board.black_king_pos = board.black_king_pos
        new_board.en_passant_target = board.en_passant_target
        new_board.halfmove_clock = board.halfmove_clock
        new_board.fullmove_number = board.fullmove_number
        new_board.current_player = board.current_player

        return new_board


# Import at end to avoid circular dependency
from chess_engine import Piece
