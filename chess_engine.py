"""
Chess Engine - Implements full chess rules and FEN notation
"""

from enum import Enum
from typing import List, Tuple, Optional, Dict, Set


class PieceType(Enum):
    PAWN = 'P'
    KNIGHT = 'N'
    BISHOP = 'B'
    ROOK = 'R'
    QUEEN = 'Q'
    KING = 'K'


class Color(Enum):
    WHITE = 'white'
    BLACK = 'black'


class Piece:
    def __init__(self, piece_type: PieceType, color: Color):
        self.type = piece_type
        self.color = color
        self.moved = False  # Tracks for castling/pawn

    def __repr__(self):
        symbol = self.type.value
        return symbol if self.color == Color.WHITE else symbol.lower()

    def to_dict(self):
        return {
            'type': self.type.name.lower(),
            'color': self.color.value,
            'moved': self.moved
        }


class ChessBoard:
    def __init__(self):
        self.board: List[List[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
        self.white_king_pos = (7, 4)
        self.black_king_pos = (0, 4)
        self.en_passant_target: Optional[Tuple[int, int]] = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.current_player = Color.WHITE
        self._setup_initial_position()

    def _setup_initial_position(self):
        """Setup standard chess starting position"""
        # Pawns
        for col in range(8):
            self.board[1][col] = Piece(PieceType.PAWN, Color.BLACK)
            self.board[6][col] = Piece(PieceType.PAWN, Color.WHITE)

        # Pieces
        pieces_row = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK
        ]
        for col, piece_type in enumerate(pieces_row):
            self.board[0][col] = Piece(piece_type, Color.BLACK)
            self.board[7][col] = Piece(piece_type, Color.WHITE)

    def is_valid_position(self, row: int, col: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        if self.is_valid_position(row, col):
            return self.board[row][col]
        return None

    def set_piece(self, row: int, col: int, piece: Optional[Piece]):
        if self.is_valid_position(row, col):
            self.board[row][col] = piece

    def get_all_pieces(self, color: Color) -> List[Tuple[Piece, int, int]]:
        pieces = []
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece and piece.color == color:
                    pieces.append((piece, row, col))
        return pieces

    def is_square_attacked(self, row: int, col: int, by_color: Color) -> bool:
        """Check if a square is attacked by a color"""
        for piece, p_row, p_col in self.get_all_pieces(by_color):
            if piece.type == PieceType.PAWN:
                if self._pawn_can_attack(p_row, p_col, row, col, by_color):
                    return True
            else:
                moves = self._get_piece_moves(piece, p_row, p_col, check_turn=False)
                if (row, col) in moves:
                    return True
        return False

    def _pawn_can_attack(self, from_row: int, from_col: int, to_row: int, to_col: int, color: Color) -> bool:
        """Check if pawn can attack a square"""
        direction = -1 if color == Color.WHITE else 1
        if to_row == from_row + direction and abs(to_col - from_col) == 1:
            return True
        return False

    def _get_piece_moves(self, piece: Piece, row: int, col: int, check_turn: bool = True) -> Set[Tuple[int, int]]:
        """Get all pseudo-legal moves for a piece"""
        moves = set()

        if check_turn and piece.color != self.current_player:
            return moves

        if piece.type == PieceType.PAWN:
            moves = self._get_pawn_moves(piece, row, col)
        elif piece.type == PieceType.KNIGHT:
            moves = self._get_knight_moves(row, col)
        elif piece.type == PieceType.BISHOP:
            moves = self._get_sliding_moves(row, col, [(1, 1), (1, -1), (-1, 1), (-1, -1)])
        elif piece.type == PieceType.ROOK:
            moves = self._get_sliding_moves(row, col, [(1, 0), (-1, 0), (0, 1), (0, -1)])
        elif piece.type == PieceType.QUEEN:
            moves = self._get_sliding_moves(row, col, [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)])
        elif piece.type == PieceType.KING:
            moves = self._get_king_moves(row, col)

        return moves

    def _get_pawn_moves(self, pawn: Piece, row: int, col: int) -> Set[Tuple[int, int]]:
        moves = set()
        direction = -1 if pawn.color == Color.WHITE else 1
        new_row = row + direction

        # Forward move
        if self.is_valid_position(new_row, col) and self.get_piece(new_row, col) is None:
            moves.add((new_row, col))

            # Double move from starting position
            if not pawn.moved:
                double_row = row + 2 * direction
                if self.get_piece(double_row, col) is None:
                    moves.add((double_row, col))

        # Captures
        for d_col in [-1, 1]:
            capture_col = col + d_col
            if self.is_valid_position(new_row, capture_col):
                target = self.get_piece(new_row, capture_col)
                if target and target.color != pawn.color:
                    moves.add((new_row, capture_col))

                # En passant
                if self.en_passant_target == (new_row, capture_col):
                    moves.add((new_row, capture_col))

        return moves

    def _get_knight_moves(self, row: int, col: int) -> Set[Tuple[int, int]]:
        moves = set()
        knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
        for d_row, d_col in knight_moves:
            new_row, new_col = row + d_row, col + d_col
            if self.is_valid_position(new_row, new_col):
                target = self.get_piece(new_row, new_col)
                if target is None or target.color != self.get_piece(row, col).color:
                    moves.add((new_row, new_col))
        return moves

    def _get_sliding_moves(self, row: int, col: int, directions: List[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        moves = set()
        piece = self.get_piece(row, col)
        for d_row, d_col in directions:
            new_row, new_col = row + d_row, col + d_col
            while self.is_valid_position(new_row, new_col):
                target = self.get_piece(new_row, new_col)
                if target is None:
                    moves.add((new_row, new_col))
                else:
                    if target.color != piece.color:
                        moves.add((new_row, new_col))
                    break
                new_row += d_row
                new_col += d_col
        return moves

    def _get_king_moves(self, row: int, col: int) -> Set[Tuple[int, int]]:
        moves = set()
        for d_row in [-1, 0, 1]:
            for d_col in [-1, 0, 1]:
                if d_row == 0 and d_col == 0:
                    continue
                new_row, new_col = row + d_row, col + d_col
                if self.is_valid_position(new_row, new_col):
                    target = self.get_piece(new_row, new_col)
                    if target is None or target.color != self.get_piece(row, col).color:
                        moves.add((new_row, new_col))

        # Castling
        king = self.get_piece(row, col)
        if not king.moved and not self.is_in_check(king.color):
            # Kingside castling
            rook_col = 7
            if (rook := self.get_piece(row, rook_col)) and not rook.moved:
                if all(self.get_piece(row, c) is None for c in [5, 6]):
                    moves.add((row, 6))
            # Queenside castling
            rook_col = 0
            if (rook := self.get_piece(row, rook_col)) and not rook.moved:
                if all(self.get_piece(row, c) is None for c in [1, 2, 3]):
                    moves.add((row, 2))

        return moves

    def get_legal_moves(self, row: int, col: int) -> Set[Tuple[int, int]]:
        """Get legal moves for a piece (excludes moves that leave king in check)"""
        piece = self.get_piece(row, col)
        if not piece or piece.color != self.current_player:
            return set()

        pseudo_legal = self._get_piece_moves(piece, row, col)
        legal_moves = set()

        for to_row, to_col in pseudo_legal:
            if self._is_move_legal(row, col, to_row, to_col):
                legal_moves.add((to_row, to_col))

        return legal_moves

    def _is_move_legal(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Check if move leaves king safe"""
        # Make move temporarily
        piece = self.get_piece(from_row, from_col)
        captured = self.get_piece(to_row, to_col)
        self.set_piece(from_row, from_col, None)
        self.set_piece(to_row, to_col, piece)

        # Update king position if moving king
        if piece.type == PieceType.KING:
            if piece.color == Color.WHITE:
                self.white_king_pos = (to_row, to_col)
            else:
                self.black_king_pos = (to_row, to_col)

        # Check if in check
        in_check = self.is_in_check(piece.color)

        # Undo move
        self.set_piece(from_row, from_col, piece)
        self.set_piece(to_row, to_col, captured)
        if piece.type == PieceType.KING:
            if piece.color == Color.WHITE:
                self.white_king_pos = (from_row, from_col)
            else:
                self.black_king_pos = (from_row, from_col)

        return not in_check

    def is_in_check(self, color: Color) -> bool:
        """Check if player is in check"""
        king_pos = self.white_king_pos if color == Color.WHITE else self.black_king_pos
        enemy_color = Color.BLACK if color == Color.WHITE else Color.WHITE
        return self.is_square_attacked(king_pos[0], king_pos[1], enemy_color)

    def make_move(self, from_row: int, from_col: int, to_row: int, to_col: int, promotion_piece: Optional[str] = None) -> bool:
        """Make a move and return success"""
        piece = self.get_piece(from_row, from_col)
        if not piece or piece.color != self.current_player:
            return False

        legal_moves = self.get_legal_moves(from_row, from_col)
        if (to_row, to_col) not in legal_moves:
            return False

        # Handle captures
        captured = self.get_piece(to_row, to_col)

        # Handle en passant
        if piece.type == PieceType.PAWN and (to_row, to_col) == self.en_passant_target:
            en_passant_pawn_row = from_row
            self.set_piece(en_passant_pawn_row, to_col, None)
            captured = True

        # Handle pawn promotion
        if piece.type == PieceType.PAWN and (to_row == 0 or to_row == 7):
            if promotion_piece:
                piece_map = {'Q': PieceType.QUEEN, 'R': PieceType.ROOK, 'B': PieceType.BISHOP, 'N': PieceType.KNIGHT}
                piece = Piece(piece_map.get(promotion_piece, PieceType.QUEEN), piece.color)

        # Handle castling
        if piece.type == PieceType.KING and abs(to_col - from_col) == 2:
            if to_col > from_col:  # Kingside
                rook = self.get_piece(from_row, 7)
                self.set_piece(from_row, 7, None)
                self.set_piece(from_row, 5, rook)
                rook.moved = True
            else:  # Queenside
                rook = self.get_piece(from_row, 0)
                self.set_piece(from_row, 0, None)
                self.set_piece(from_row, 3, rook)
                rook.moved = True

        # Move piece
        piece.moved = True
        self.set_piece(from_row, from_col, None)
        self.set_piece(to_row, to_col, piece)

        # Update king position
        if piece.type == PieceType.KING:
            if piece.color == Color.WHITE:
                self.white_king_pos = (to_row, to_col)
            else:
                self.black_king_pos = (to_row, to_col)

        # Update en passant target
        self.en_passant_target = None
        if piece.type == PieceType.PAWN and abs(to_row - from_row) == 2:
            self.en_passant_target = ((from_row + to_row) // 2, to_col)

        # Update turn and clocks
        self.halfmove_clock = 0 if captured or piece.type == PieceType.PAWN else self.halfmove_clock + 1
        self.current_player = Color.BLACK if self.current_player == Color.WHITE else Color.WHITE
        if self.current_player == Color.WHITE:
            self.fullmove_number += 1

        return True

    def is_checkmate(self) -> bool:
        """Check if current player is in checkmate"""
        if not self.is_in_check(self.current_player):
            return False

        for piece, row, col in self.get_all_pieces(self.current_player):
            if self.get_legal_moves(row, col):
                return False
        return True

    def is_stalemate(self) -> bool:
        """Check if current player is in stalemate"""
        if self.is_in_check(self.current_player):
            return False

        for piece, row, col in self.get_all_pieces(self.current_player):
            if self.get_legal_moves(row, col):
                return False
        return True

    def get_fen(self) -> str:
        """Convert board to FEN notation"""
        fen_parts = []

        # Board position
        for row in range(8):
            fen_row = ""
            empty = 0
            for col in range(8):
                piece = self.get_piece(row, col)
                if piece:
                    if empty:
                        fen_row += str(empty)
                        empty = 0
                    fen_row += str(piece)
                else:
                    empty += 1
            if empty:
                fen_row += str(empty)
            fen_parts.append(fen_row)

        fen = "/".join(fen_parts)
        fen += " " + ("w" if self.current_player == Color.WHITE else "b")
        fen += " " + ("-" if not self._can_castle() else self._get_castling_rights())
        fen += " " + (f"{chr(97 + self.en_passant_target[1])}{8 - self.en_passant_target[0]}" if self.en_passant_target else "-")
        fen += f" {self.halfmove_clock} {self.fullmove_number}"

        return fen

    def _can_castle(self) -> bool:
        for color in [Color.WHITE, Color.BLACK]:
            for piece, _, _ in self.get_all_pieces(color):
                if piece.type in [PieceType.KING, PieceType.ROOK] and not piece.moved:
                    return True
        return False

    def _get_castling_rights(self) -> str:
        rights = ""
        white_king = self.get_piece(7, 4)
        if white_king and not white_king.moved:
            if (rook := self.get_piece(7, 7)) and not rook.moved:
                rights += "K"
            if (rook := self.get_piece(7, 0)) and not rook.moved:
                rights += "Q"
        black_king = self.get_piece(0, 4)
        if black_king and not black_king.moved:
            if (rook := self.get_piece(0, 7)) and not rook.moved:
                rights += "k"
            if (rook := self.get_piece(0, 0)) and not rook.moved:
                rights += "q"
        return rights or "-"

    def to_dict(self) -> Dict:
        """Serialize board state"""
        pieces = []
        for row in range(8):
            for col in range(8):
                piece = self.get_piece(row, col)
                if piece:
                    pieces.append({
                        'type': piece.type.name.lower(),
                        'color': piece.color.value,
                        'row': row,
                        'col': col
                    })
        return {
            'pieces': pieces,
            'fen': self.get_fen(),
            'current_player': self.current_player.value,
            'in_check': self.is_in_check(self.current_player),
            'checkmate': self.is_checkmate(),
            'stalemate': self.is_stalemate()
        }
