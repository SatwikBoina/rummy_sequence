from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import random
import json
import os

app = Flask(__name__)
CORS(app)

from rummy import rummy_bp
app.register_blueprint(rummy_bp)

# In-memory game store (for production, use Redis or a DB)
games = {}

SUITS = ['diamonds', 'hearts', 'clubs', 'spades']
RANKS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]  # 11=J, 12=Q, 13=K, 14=A
RANK_NAMES = {2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K',14:'A'}

def create_deck():
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({'suit': suit, 'rank': rank})
    random.shuffle(deck)
    return deck

def deal_cards(players, deck):
    hands = {p: [] for p in players}
    for i, card in enumerate(deck):
        player = players[i % len(players)]
        hands[player].append(card)
    return hands

def find_starter(hands):
    """Find who has Diamond 7"""
    for player_id, player in hands.items():
        for card in player:
            if card['suit'] == 'diamonds' and card['rank'] == 7:
                return player_id
    return None

def get_valid_moves(hand, board):
    """
    Board structure: {'diamonds': [7], 'hearts': [], 'clubs': [], 'spades': []}
    Each suit list contains ranks played (always extending outward from 7)
    """
    valid = []
    for card in hand:
        suit = card['suit']
        rank = card['rank']
        played = board[suit]
        if not played:
            # Can only play 7 of this suit if 7 is available
            if rank == 7:
                valid.append(card)
        else:
            min_rank = min(played)
            max_rank = max(played)
            if rank == min_rank - 1 or rank == max_rank + 1:
                valid.append(card)
    return valid

def check_winner(players):
    for player_id, player in hands.items():
        if len(player['hand']) == 0:
            return player_id
    return None

@app.route('/api/create_game', methods=['POST'])
def create_game():
    data = request.json
    host_name = data.get('host_name', 'Host')
    game_id = str(uuid.uuid4())[:8].upper()
    
    games[game_id] = {
        'id': game_id,
        'status': 'waiting',  # waiting, playing, finished
        'host': None,
        'players': {},  # player_id -> {name, hand, passed_count}
        'player_order': [],
        'current_turn_index': 0,
        'board': {'diamonds': [], 'hearts': [], 'clubs': [], 'spades': []},
        'winner': None,
        'rankings': []
    }
    
    # Host joins automatically
    player_id = str(uuid.uuid4())[:8]
    games[game_id]['players'][player_id] = {'name': host_name, 'hand': [], 'passed': False}
    games[game_id]['player_order'].append(player_id)
    games[game_id]['host'] = player_id
    
    return jsonify({'game_id': game_id, 'player_id': player_id})

@app.route('/api/join_game', methods=['POST'])
def join_game():
    data = request.json
    game_id = data.get('game_id', '').upper()
    player_name = data.get('player_name', 'Player')
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    if game['status'] != 'waiting':
        return jsonify({'error': 'Game already started'}), 400
    if len(game['players']) >= 6:
        return jsonify({'error': 'Game is full (max 6 players)'}), 400
    
    player_id = str(uuid.uuid4())[:8]
    game['players'][player_id] = {'name': player_name, 'hand': [], 'passed': False}
    game['player_order'].append(player_id)
    
    return jsonify({'game_id': game_id, 'player_id': player_id})

@app.route('/api/start_game', methods=['POST'])
def start_game():
    data = request.json
    game_id = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    if game['host'] != player_id:
        return jsonify({'error': 'Only the host can start the game'}), 403
    if len(game['players']) < 2:
        return jsonify({'error': 'Need at least 2 players'}), 400
    if game['status'] != 'waiting':
        return jsonify({'error': 'Game already started'}), 400
    
    deck = create_deck()
    hands = deal_cards(game['player_order'], deck)
    
    for pid in game['player_order']:
        game['players'][pid]['hand'] = hands[pid]
    
    starter = find_starter(hands)
    starter_index = game['player_order'].index(starter)
    game['current_turn_index'] = starter_index
    game['status'] = 'playing'
    game['board'] = {'diamonds': [7], 'hearts': [], 'clubs': [], 'spades': []}
    
    # Remove diamond 7 from starter's hand
    game['players'][starter]['hand'] = [
        c for c in game['players'][starter]['hand']
        if not (c['suit'] == 'diamonds' and c['rank'] == 7)
    ]
    
    return jsonify({'success': True})

@app.route('/api/play_card', methods=['POST'])
def play_card():
    data = request.json
    game_id = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    card = data.get('card')  # {suit, rank}
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    if game['status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    current_player = game['player_order'][game['current_turn_index']]
    if player_id != current_player:
        return jsonify({'error': 'Not your turn'}), 403
    
    hand = game['players'][player_id]['hand']
    valid_moves = get_valid_moves(hand, game['board'])
    
    # Check card is in valid moves
    match = None
    for vm in valid_moves:
        if vm['suit'] == card['suit'] and vm['rank'] == card['rank']:
            match = vm
            break
    
    if not match:
        return jsonify({'error': 'Invalid move'}), 400
    
    # Play the card
    game['players'][player_id]['hand'] = [c for c in hand if not (c['suit'] == card['suit'] and c['rank'] == card['rank'])]
    game['board'][card['suit']].append(card['rank'])
    game['players'][player_id]['passed'] = False
    
    # Check winner
    winner = check_winner(game['players'])
    if winner:
        game['status'] = 'finished'
        game['winner'] = winner
        if winner not in game['rankings']:
            game['rankings'].append(winner)
    else:
        # Add to rankings if hand empty (shouldn't happen mid-game but safety)
        _advance_turn(game)
    
    return jsonify({'success': True})

@app.route('/api/pass_turn', methods=['POST'])
def pass_turn():
    data = request.json
    game_id = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    current_player = game['player_order'][game['current_turn_index']]
    if player_id != current_player:
        return jsonify({'error': 'Not your turn'}), 403
    
    hand = game['players'][player_id]['hand']
    valid_moves = get_valid_moves(hand, game['board'])
    if valid_moves:
        return jsonify({'error': 'You have valid moves, cannot pass'}), 400
    
    game['players'][player_id]['passed'] = True
    _advance_turn(game)
    return jsonify({'success': True})

def _advance_turn(game):
    n = len(game['player_order'])
    next_idx = (game['current_turn_index'] + 1) % n
    # Skip players with empty hands
    for _ in range(n):
        pid = game['player_order'][next_idx]
        if len(game['players'][pid]['hand']) > 0:
            game['current_turn_index'] = next_idx
            return
        next_idx = (next_idx + 1) % n

@app.route('/api/game_state', methods=['GET'])
def game_state():
    game_id = request.args.get('game_id', '').upper()
    player_id = request.args.get('player_id')
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    current_player_id = game['player_order'][game['current_turn_index']] if game['player_order'] else None
    my_hand = game['players'].get(player_id, {}).get('hand', [])
    valid_moves = get_valid_moves(my_hand, game['board']) if game['status'] == 'playing' else []
    
    players_info = []
    for pid in game['player_order']:
        p = game['players'][pid]
        players_info.append({
            'id': pid,
            'name': p['name'],
            'card_count': len(p['hand']),
            'is_current': pid == current_player_id,
            'is_me': pid == player_id,
            'passed': p.get('passed', False)
        })
    
    return jsonify({
        'game_id': game_id,
        'status': game['status'],
        'host': game['host'],
        'players': players_info,
        'board': game['board'],
        'my_hand': my_hand,
        'valid_moves': valid_moves,
        'current_player_id': current_player_id,
        'is_my_turn': current_player_id == player_id,
        'winner': game['winner'],
        'winner_name': game['players'][game['winner']]['name'] if game['winner'] else None,
        'player_count': len(game['players'])
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)