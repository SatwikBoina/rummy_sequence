from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import random
import os

app = Flask(__name__)
CORS(app)

from rummy import rummy_bp
app.register_blueprint(rummy_bp)

games = {}

SUITS = ['diamonds', 'hearts', 'clubs', 'spades']
RANKS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

def create_deck():
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({'suit': suit, 'rank': rank})
    random.shuffle(deck)
    return deck

def deal_cards(player_ids, deck):
    hands = {p: [] for p in player_ids}
    for i, card in enumerate(deck):
        pid = player_ids[i % len(player_ids)]
        hands[pid].append(card)
    return hands

def find_starter(hands):
    for player_id, hand in hands.items():
        for card in hand:
            if card['suit'] == 'diamonds' and card['rank'] == 7:
                return player_id
    return None

def get_valid_moves(hand, board):
    valid = []
    for card in hand:
        suit = card['suit']
        rank = card['rank']
        played = board[suit]
        if not played:
            if rank == 7:
                valid.append(card)
        else:
            min_rank = min(played)
            max_rank = max(played)
            if rank == min_rank - 1 or rank == max_rank + 1:
                valid.append(card)
    return valid

def check_winner(players):
    for player_id, player in players.items():
        if len(player['hand']) == 0:
            return player_id
    return None

def advance_turn(game):
    n = len(game['player_order'])
    for i in range(1, n + 1):
        next_idx = (game['current_turn_index'] + i) % n
        pid = game['player_order'][next_idx]
        if len(game['players'][pid]['hand']) > 0:
            game['current_turn_index'] = next_idx
            return

@app.route('/api/create_game', methods=['POST'])
def create_game():
    data = request.json
    host_name = data.get('host_name', 'Host')
    game_id = str(uuid.uuid4())[:8].upper()
    player_id = str(uuid.uuid4())[:8]
    games[game_id] = {
        'id': game_id, 'status': 'waiting', 'host': player_id,
        'players': {player_id: {'name': host_name, 'hand': [], 'passed': False}},
        'player_order': [player_id], 'current_turn_index': 0,
        'board': {'diamonds': [], 'hearts': [], 'clubs': [], 'spades': []},
        'winner': None, 'rankings': []
    }
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
    game['current_turn_index'] = game['player_order'].index(starter)
    game['status'] = 'playing'
    game['board'] = {'diamonds': [7], 'hearts': [], 'clubs': [], 'spades': []}
    game['players'][starter]['hand'] = [
        c for c in game['players'][starter]['hand']
        if not (c['suit'] == 'diamonds' and c['rank'] == 7)
    ]
    # Starter's Diamond 7 is auto-placed, advance to next player
    advance_turn(game)
    return jsonify({'success': True})

@app.route('/api/play_card', methods=['POST'])
def play_card():
    data = request.json
    game_id = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    card = data.get('card')
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
    match = next((c for c in valid_moves if c['suit'] == card['suit'] and c['rank'] == card['rank']), None)
    if not match:
        return jsonify({'error': 'Invalid move'}), 400
    game['players'][player_id]['hand'] = [
        c for c in hand if not (c['suit'] == card['suit'] and c['rank'] == card['rank'])
    ]
    game['board'][card['suit']].append(card['rank'])
    game['players'][player_id]['passed'] = False
    winner = check_winner(game['players'])
    if winner:
        game['status'] = 'finished'
        game['winner'] = winner
        if winner not in game['rankings']:
            game['rankings'].append(winner)
    else:
        advance_turn(game)
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
    advance_turn(game)
    return jsonify({'success': True})

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
            'id': pid, 'name': p['name'], 'card_count': len(p['hand']),
            'is_current': pid == current_player_id,
            'is_me': pid == player_id, 'passed': p.get('passed', False)
        })
    return jsonify({
        'game_id': game_id, 'status': game['status'], 'host': game['host'],
        'players': players_info, 'board': game['board'],
        'my_hand': my_hand, 'valid_moves': valid_moves,
        'current_player_id': current_player_id,
        'is_my_turn': current_player_id == player_id,
        'winner': game['winner'],
        'winner_name': game['players'][game['winner']]['name'] if game['winner'] else None,
        'player_count': len(game['players'])
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)