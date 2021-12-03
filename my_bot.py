import chess.engine
import random
from reconchess import *
import os
import pandas as pd
import math

os.environ['STOCKFISH_EXECUTABLE'] = 'C:/Users/esq60/stockfish_14.1_win_x64_avx2/stockfish_14.1_win_x64_avx2.exe'
STOCKFISH_ENV_VAR = 'STOCKFISH_EXECUTABLE'


class MarcBot(Player):
    """
    TroutBot uses the Stockfish chess engine to choose moves. In order to run TroutBot you'll need to download
    Stockfish from https://stockfishchess.org/download/ and create an environment variable called STOCKFISH_EXECUTABLE
    that is the path to the downloaded Stockfish executable.
    """

    def __init__(self):
        self.board = None
        self.color = None
        self.my_piece_captured_square = None

        # Perimeter squares so sense doesn't pick one of these
        self.perimeter = [1,2,3,4,5,6,7,8,16,24,32,40,48,56,64,63,62,61,60,59,58,57,49,41,33,25,17,9]
        
        # Reward for piece capture
        self.piece_val = {
            1 : 1,
            2 : 3,
            3 : 3,
            4 : 5,
            5 : 9,
            6 : 100,
            None :0
        }

        # Reward for being in check
        self.check_val = {
            True : -80,
            False : 0
        } 




    def fwd_search(self,board,depth_start,piece_val,check_val, disc):

        # Set value to correctly set up FEN board
        if self.color == True:
            color_add = " w"
        else:
            color_add = " b"
        
        def fwd_search_recurse(board, depth,max_depth, disc):

            # Initialize Values
            max_val = 0
            array_val = []
            board_new = chess.Board(board.board_fen() + color_add)
            
            # Sparse Sample for additional levels of depth
            k_val = int(len(list(board_new.legal_moves))/math.pow(2,max_depth-depth))
            moves_sample = random.choices(list(board_new.legal_moves),k=k_val)
            
            # For each move in sample, conduct evaluation and forward search.
            for moves in moves_sample:

                # Initialize board
                board_new = chess.Board(board.board_fen() + color_add)

                capture_val = piece_val[board_new.piece_type_at(moves.to_square)]

                board_new.push(moves)

                self_check_val = check_val[board_new.is_check()]
                pos_val = capture_val + self_check_val

                # Update maximum utility if best
                if pos_val > max_val:
                    max_val = pos_val

                if depth > 0:
                    # If not at max depth, recursively search
                    new_num = fwd_search_recurse(board_new, depth-1,depth_start, disc)[0]
                    
                    array_val.append([depth,moves,new_num])

                    max_val = max_val + math.pow(disc,(max_depth-depth))* new_num
                    
            return max_val, array_val

        # Initialize arrays
        out_arr = []
        out_arr_all = []
        for moves in list(board.legal_moves):
            
            # Initialize board
            board_start = chess.Board(board.board_fen() + color_add)
            
            # Make next move
            board_start.push(moves)

            # Recursively search following moves
            next_move = fwd_search_recurse(board_start, depth_start,depth_start, disc)

            # Record results
            out_arr.append([moves,next_move[0]])
            out_arr_all.append(next_move[1])
            
        out_filt = pd.DataFrame(out_arr)
        
        out_filt_max = out_filt.iloc[out_filt[1].idxmax()][0]
        
        return out_filt_max


    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.board = board
        self.color = color

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        # if the opponent captured our piece, remove it from our board.
        self.my_piece_captured_square = capture_square
        if captured_my_piece:
            self.board.remove_piece_at(capture_square)

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
            Optional[Square]:
        # if our piece was just captured, sense where it was captured
        if self.my_piece_captured_square:
            return self.my_piece_captured_square

        # otherwise, just randomly choose a sense action, but don't sense on a square where our pieces are located
        for square, piece in self.board.piece_map().items():
            if piece.color == self.color:
                sense_actions.remove(square)
        #print(type(sense_actions), type(self.perimeter))
        for square in sense_actions:
            if square in self.perimeter:
                sense_actions.remove(square)
        #sense_actions = [i for i in sense_actions if not any([e for e in self.perimeter if e in i])]
        #print(sense_actions)
        return random.choice(sense_actions)

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        # add the pieces in the sense result to our board
        for square, piece in sense_result:
            self.board.set_piece_at(square, piece)

    

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        # if we might be able to take the king, try to
        enemy_king_square = self.board.king(not self.color)
        print(enemy_king_square)
        if enemy_king_square:
            
            # if there are any ally pieces that can take king, execute one of those moves
            enemy_king_attackers = self.board.attackers(self.color, enemy_king_square)
            if enemy_king_attackers:
                print("king seen")
                attacker_square = enemy_king_attackers.pop()
                return chess.Move(attacker_square, enemy_king_square)

        # otherwise, try to move with the stockfish chess engine
        try:
            self.board.turn = self.color
            self.board.clear_stack()
            
            # Execute forward search.  Tree depth is depth_start + 1.
            
            move1 = self.fwd_search(board = self.board,depth_start = 2,piece_val = self.piece_val,check_val = self.check_val, disc = 0.75)

            move_val = chess.Move.from_uci(move1.uci())
            
            return move_val

        except chess.engine.EngineTerminatedError:
            print('Stockfish Engine died')
        except chess.engine.EngineError:
            print('Stockfish Engine bad state at "{}"'.format(self.board.fen()))

        # if all else fails, pass
        return None

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        # if a move was executed, apply it to our board
        if taken_move is not None:
            self.board.push(taken_move)

        print(requested_move, taken_move)

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        pass