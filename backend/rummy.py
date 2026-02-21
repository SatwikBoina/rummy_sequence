from flask import Blueprint, request, jsonify
import uuid
import random

rummy_bp = Blueprint('rummy', __name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SUITS = ['diamonds', 'hearts', 'clubs', 'spades']
RANKS = [1,2,3,4,5,6,7,8,9,10,11,12,13]  # 1=A,11=J,12=Q,13=K
RANK_NAMES = {1:'A',2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',11:'J',12:'Q',13:'K'}
RANK_POINTS = {1:10,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,10:10,11:10,12:10,13:10}

VARIANT_CARDS = {'indian': 13, 'gin': 10, 'classic': 7}
VARIANT_DECKS  = {'indian': 2,  'gin': 1,  'classic': 1}

rummy_games = {}

# ── Deck helpers ───────────────────────────────────────────────────────────────
def make_deck(num_decks=1, include_joker=False):
    deck = []
    for _ in range(num_decks):
        for suit in SUITS:
            for rank in RANKS:
                deck.append({'suit': suit, 'rank': rank, 'id': str(uuid.uuid4())[:6]})
        if include_joker:
            deck.append({'suit': 'joker', 'rank': 0, 'id': str(uuid.uuid4())[:6]})
    random.shuffle(deck)
    return deck

def card_points(card):
    return RANK_POINTS.get(card['rank'], 10)

# ── Meld validation ────────────────────────────────────────────────────────────
def is_set(cards):
    """3-4 cards of same rank, different suits (jokers wild in indian)"""
    if len(cards) < 3 or len(cards) > 4:
        return False
    ranks = [c['rank'] for c in cards if c['suit'] != 'joker']
    suits = [c['suit'] for c in cards if c['suit'] != 'joker']
    if len(set(ranks)) != 1:
        return False
    if len(suits) != len(set(suits)):
        return False  # duplicate suits
    return True

def is_run(cards):
    """3+ consecutive cards of same suit"""
    if len(cards) < 3:
        return False
    real = [c for c in cards if c['suit'] != 'joker']
    jokers = len(cards) - len(real)
    if not real:
        return False
    suits = set(c['suit'] for c in real)
    if len(suits) != 1:
        return False
    ranks = sorted(c['rank'] for c in real)
    # check gaps fillable by jokers
    gaps = 0
    for i in range(1, len(ranks)):
        diff = ranks[i] - ranks[i-1] - 1
        if diff < 0:
            return False  # duplicates
        gaps += diff
    return gaps <= jokers

def is_valid_meld(cards):
    return is_set(cards) or is_run(cards)

def hand_deadwood(hand, melds):
    """Return unmelded cards and their point total"""
    melded_ids = set()
    for meld in melds:
        for c in meld:
            melded_ids.add(c['id'])
    unmelded = [c for c in hand if c['id'] not in melded_ids]
    points = sum(card_points(c) for c in unmelded)
    return unmelded, points

# ── Routes ─────────────────────────────────────────────────────────────────────
@rummy_bp.route('/api/rummy/create', methods=['POST'])
def create_rummy():
    data = request.json
    host_name = data.get('host_name', 'Host').strip()
    if len(host_name) < 6:
        return jsonify({'error': 'Username must be at least 6 characters'}), 400

    variant   = data.get('variant', 'classic')       # indian | gin | classic
    max_players = int(data.get('max_players', 4))     # 2-6
    scoring   = data.get('scoring', 'loser_pays')     # loser_pays | first_100_loses | target_wins
    target    = int(data.get('target', 100))

    if variant not in VARIANT_CARDS:
        variant = 'classic'
    max_players = max(2, min(6, max_players))

    game_id   = str(uuid.uuid4())[:8].upper()
    player_id = str(uuid.uuid4())[:8]

    rummy_games[game_id] = {
        'id': game_id,
        'status': 'waiting',
        'variant': variant,
        'max_players': max_players,
        'scoring': scoring,
        'target': target,
        'host': player_id,
        'players': {
            player_id: {'name': host_name, 'hand': [], 'melds': [], 'score': 0, 'went_out': False}
        },
        'player_order': [player_id],
        'current_turn_index': 0,
        'deck': [],
        'discard_pile': [],
        'round': 1,
        'drawn_this_turn': False,
        'round_over': False,
        'winner': None,
        'game_over': False,
    }
    return jsonify({'game_id': game_id, 'player_id': player_id})


@rummy_bp.route('/api/rummy/join', methods=['POST'])
def join_rummy():
    data = request.json
    game_id     = data.get('game_id', '').upper()
    player_name = data.get('player_name', '').strip()

    if len(player_name) < 6:
        return jsonify({'error': 'Username must be at least 6 characters'}), 400
    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404

    game = rummy_games[game_id]
    if game['status'] != 'waiting':
        return jsonify({'error': 'Game already started'}), 400
    if len(game['players']) >= game['max_players']:
        return jsonify({'error': f"Game is full (max {game['max_players']} players)"}), 400

    # Check duplicate names
    existing = [p['name'].lower() for p in game['players'].values()]
    if player_name.lower() in existing:
        return jsonify({'error': 'Name already taken in this game'}), 400

    player_id = str(uuid.uuid4())[:8]
    game['players'][player_id] = {'name': player_name, 'hand': [], 'melds': [], 'score': 0, 'went_out': False}
    game['player_order'].append(player_id)
    return jsonify({'game_id': game_id, 'player_id': player_id})


@rummy_bp.route('/api/rummy/start', methods=['POST'])
def start_rummy():
    data = request.json
    game_id   = data.get('game_id', '').upper()
    player_id = data.get('player_id')

    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404
    game = rummy_games[game_id]
    if game['host'] != player_id:
        return jsonify({'error': 'Only host can start'}), 403
    if len(game['players']) < 2:
        return jsonify({'error': 'Need at least 2 players'}), 400

    _deal_round(game)
    game['status'] = 'playing'
    return jsonify({'success': True})


def _deal_round(game):
    num_decks = VARIANT_DECKS[game['variant']]
    cards_each = VARIANT_CARDS[game['variant']]
    deck = make_deck(num_decks)

    for pid in game['player_order']:
        game['players'][pid]['hand'] = deck[:cards_each]
        game['players'][pid]['melds'] = []
        game['players'][pid]['went_out'] = False
        deck = deck[cards_each:]

    game['deck'] = deck[1:]          # rest is draw pile
    game['discard_pile'] = [deck[0]] # first card face-up
    game['drawn_this_turn'] = False
    game['round_over'] = False
    game['current_turn_index'] = (game.get('current_turn_index', 0)) % len(game['player_order'])


@rummy_bp.route('/api/rummy/draw', methods=['POST'])
def draw_card():
    data = request.json
    game_id   = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    source    = data.get('source', 'deck')  # 'deck' or 'discard'

    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404
    game = rummy_games[game_id]
    if game['status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400

    current = game['player_order'][game['current_turn_index']]
    if player_id != current:
        return jsonify({'error': 'Not your turn'}), 403
    if game['drawn_this_turn']:
        return jsonify({'error': 'Already drew this turn'}), 400

    if source == 'discard':
        if not game['discard_pile']:
            return jsonify({'error': 'Discard pile is empty'}), 400
        card = game['discard_pile'].pop()
    else:
        if not game['deck']:
            # Reshuffle discard (keep top)
            top = game['discard_pile'][-1] if game['discard_pile'] else None
            game['deck'] = game['discard_pile'][:-1] if top else game['discard_pile'][:]
            random.shuffle(game['deck'])
            game['discard_pile'] = [top] if top else []
        if not game['deck']:
            return jsonify({'error': 'No cards left'}), 400
        card = game['deck'].pop(0)

    game['players'][player_id]['hand'].append(card)
    game['drawn_this_turn'] = True
    return jsonify({'success': True, 'card': card})


@rummy_bp.route('/api/rummy/discard', methods=['POST'])
def discard_card():
    data = request.json
    game_id   = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    card_id   = data.get('card_id')

    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404
    game = rummy_games[game_id]

    current = game['player_order'][game['current_turn_index']]
    if player_id != current:
        return jsonify({'error': 'Not your turn'}), 403
    if not game['drawn_this_turn']:
        return jsonify({'error': 'Draw a card first'}), 400

    hand = game['players'][player_id]['hand']
    card = next((c for c in hand if c['id'] == card_id), None)
    if not card:
        return jsonify({'error': 'Card not in hand'}), 400

    game['players'][player_id]['hand'] = [c for c in hand if c['id'] != card_id]
    game['discard_pile'].append(card)
    game['drawn_this_turn'] = False

    # Advance turn
    n = len(game['player_order'])
    game['current_turn_index'] = (game['current_turn_index'] + 1) % n
    return jsonify({'success': True})


@rummy_bp.route('/api/rummy/declare_melds', methods=['POST'])
def declare_melds():
    """Player submits their meld groups to go out"""
    data = request.json
    game_id   = data.get('game_id', '').upper()
    player_id = data.get('player_id')
    melds     = data.get('melds', [])  # list of lists of card dicts

    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404
    game = rummy_games[game_id]

    current = game['player_order'][game['current_turn_index']]
    if player_id != current:
        return jsonify({'error': 'Not your turn'}), 403
    if not game['drawn_this_turn']:
        return jsonify({'error': 'Draw a card first'}), 400

    # Validate each meld
    for meld in melds:
        if not is_valid_meld(meld):
            return jsonify({'error': f'Invalid meld: {[RANK_NAMES[c["rank"]] + c["suit"][0].upper() for c in meld]}'}), 400

    # Check all meld cards are actually in hand
    hand = game['players'][player_id]['hand']
    hand_ids = {c['id'] for c in hand}
    meld_ids = [c['id'] for meld in melds for c in meld]
    if len(set(meld_ids)) != len(meld_ids):
        return jsonify({'error': 'Duplicate cards in melds'}), 400
    if not all(cid in hand_ids for cid in meld_ids):
        return jsonify({'error': 'Meld contains cards not in your hand'}), 400

    game['players'][player_id]['melds'] = melds

    unmelded, points = hand_deadwood(hand, melds)

    # Going out: unmelded must be 1 card (which gets discarded) or 0
    if len(unmelded) > 1:
        return jsonify({'error': f'You still have {len(unmelded)} unmelded cards ({points} pts). Meld more or discard one.'}), 400

    # Player goes out!
    if unmelded:
        game['discard_pile'].append(unmelded[0])
        game['players'][player_id]['hand'] = [c for c in hand if c['id'] != unmelded[0]['id']]

    game['players'][player_id]['went_out'] = True
    game['round_over'] = True
    game['drawn_this_turn'] = False

    _score_round(game, player_id)
    return jsonify({'success': True})


def _score_round(game, winner_id):
    scoring = game['scoring']

    if scoring == 'loser_pays':
        # Winner gets 0; losers get points equal to deadwood in their hand
        for pid, p in game['players'].items():
            if pid == winner_id:
                continue
            _, pts = hand_deadwood(p['hand'], p['melds'])
            p['score'] += pts

    elif scoring == 'first_100_loses':
        # Losers accumulate deadwood; first to 100 is eliminated / game over
        for pid, p in game['players'].items():
            if pid == winner_id:
                continue
            _, pts = hand_deadwood(p['hand'], p['melds'])
            p['score'] += pts
        # Check if anyone hit target
        for pid, p in game['players'].items():
            if p['score'] >= game['target']:
                game['game_over'] = True
                # Winner is player with lowest score
                game['winner'] = min(game['players'].items(), key=lambda x: x[1]['score'])[0]
                game['status'] = 'finished'
                return

    elif scoring == 'target_wins':
        # Winner accumulates opponents' deadwood; first to target wins
        total = 0
        for pid, p in game['players'].items():
            if pid == winner_id:
                continue
            _, pts = hand_deadwood(p['hand'], p['melds'])
            total += pts
        game['players'][winner_id]['score'] += total
        if game['players'][winner_id]['score'] >= game['target']:
            game['game_over'] = True
            game['winner'] = winner_id
            game['status'] = 'finished'
            return

    # Start next round if game not over
    game['round'] += 1
    _deal_round(game)


@rummy_bp.route('/api/rummy/state', methods=['GET'])
def rummy_state():
    game_id   = request.args.get('game_id', '').upper()
    player_id = request.args.get('player_id')

    if game_id not in rummy_games:
        return jsonify({'error': 'Game not found'}), 404
    game = rummy_games[game_id]

    current_pid = game['player_order'][game['current_turn_index']] if game['player_order'] else None

    players_info = []
    for pid in game['player_order']:
        p = game['players'][pid]
        players_info.append({
            'id': pid,
            'name': p['name'],
            'card_count': len(p['hand']),
            'score': p['score'],
            'melds': p['melds'] if pid == player_id else [],
            'went_out': p['went_out'],
            'is_current': pid == current_pid,
            'is_me': pid == player_id,
        })

    top_discard = game['discard_pile'][-1] if game['discard_pile'] else None

    return jsonify({
        'game_id': game_id,
        'status': game['status'],
        'variant': game['variant'],
        'scoring': game['scoring'],
        'target': game['target'],
        'round': game['round'],
        'host': game['host'],
        'max_players': game['max_players'],
        'players': players_info,
        'my_hand': game['players'].get(player_id, {}).get('hand', []),
        'my_melds': game['players'].get(player_id, {}).get('melds', []),
        'top_discard': top_discard,
        'deck_count': len(game['deck']),
        'is_my_turn': current_pid == player_id,
        'drawn_this_turn': game['drawn_this_turn'],
        'round_over': game['round_over'],
        'game_over': game['game_over'],
        'winner': game['winner'],
        'winner_name': game['players'][game['winner']]['name'] if game['winner'] else None,
        'player_count': len(game['players']),
    })
