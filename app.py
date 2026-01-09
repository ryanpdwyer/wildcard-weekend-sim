"""Flask application for Wildcard Weekend Win Probability Simulator."""

import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request

from src.models.game import NFLGame
from src.models.roster import FantasyTeam
from src.models.bet import Bet, BetType
from src.data.loader import load_all_projections
from src.data.scoreboard_parser import parse_scoreboard_simple
from src.data.live_api import ESPNProvider, fetch_live_data
from src.simulation.monte_carlo import MonteCarloSimulator, create_default_games

app = Flask(__name__)

# Global state
projections = None
teams = None
games = None
espn_provider = None


def initialize():
    """Initialize data on startup."""
    global projections, teams, games, espn_provider

    # Load projections
    projections = load_all_projections()
    print(f"Loaded {len(projections)} player projections")

    # Load teams from scoreboard
    scoreboard_path = Path(__file__).parent / "Scoreboard.txt"
    if scoreboard_path.exists():
        teams = parse_scoreboard_simple(str(scoreboard_path))
        print(f"Loaded {len(teams)} fantasy teams")

        # Extract bets with correct draft rounds from Draft.txt
        draft_path = Path(__file__).parent / "Draft.txt"
        if draft_path.exists():
            teams = load_teams_with_draft_rounds(str(scoreboard_path), str(draft_path))
    else:
        teams = []
        print("Warning: Scoreboard.txt not found")

    # Create games with default betting lines
    games = create_default_games()
    print(f"Created {len(games)} NFL games")

    # Initialize ESPN provider
    espn_provider = ESPNProvider()


def load_teams_with_draft_rounds(scoreboard_path: str, draft_path: str):
    """Load teams and properly assign draft rounds to bets."""
    from src.data.scoreboard_parser import parse_scoreboard_simple

    teams = parse_scoreboard_simple(scoreboard_path)

    # Parse draft to get pick rounds
    draft_rounds = parse_draft_file(draft_path)

    # Update bet draft rounds
    for team in teams:
        for bet in team.bets:
            key = (team.owner, bet_to_draft_key(bet))
            if key in draft_rounds:
                bet.draft_round = draft_rounds[key]

    return teams


def parse_draft_file(filepath: str) -> dict:
    """Parse Draft.txt to get draft round for each pick."""
    import re

    with open(filepath, 'r') as f:
        content = f.read()

    # Clean line number prefixes
    content = re.sub(r'^\s*\d+→', '', content, flags=re.MULTILINE)

    draft_rounds = {}
    owners = []

    # Find header line with owners
    for line in content.split('\n'):
        if 'Ian' in line and 'Kevin' in line:
            parts = line.split('\t')
            owners = [p.strip() for p in parts[1:] if p.strip()]
            break

    # Parse round by round - rounds are separated by "Round X" at start of line
    round_pattern = re.compile(r'^Round\s+(\d+)\t(.*)$', re.MULTILINE | re.DOTALL)

    # Split content into rounds
    round_sections = re.split(r'(?=^Round\s+\d+\t)', content, flags=re.MULTILINE)

    for section in round_sections:
        if not section.strip() or not section.startswith('Round'):
            continue

        # Get round number and content
        lines = section.strip().split('\n')
        first_line = lines[0]

        round_match = re.match(r'Round\s+(\d+)\t(.*)', first_line)
        if not round_match:
            continue

        current_round = int(round_match.group(1))

        # Rejoin all lines and split by tabs to get columns
        full_section = '\n'.join(lines)
        # Remove "Round X" prefix and split remaining by tabs
        remaining = full_section[full_section.index('\t')+1:]
        columns = remaining.split('\t')

        for col_idx, pick in enumerate(columns):
            if col_idx < len(owners) and pick.strip():
                owner = owners[col_idx]
                # Clean the pick: remove quotes, normalize whitespace
                pick_clean = pick.strip().replace('"', '').replace('\n', ' ').strip()
                # Normalize multiple spaces to single space
                pick_clean = re.sub(r'\s+', ' ', pick_clean)
                draft_rounds[(owner, pick_clean)] = current_round

    return draft_rounds


def bet_to_draft_key(bet: Bet) -> str:
    """Convert bet to a key that matches draft format (space-separated, matching parse_draft_file)."""
    # Format line as integer if it's a whole number (e.g., -3.0 -> -3)
    line = int(bet.line) if bet.line == int(bet.line) else bet.line

    if bet.bet_type == BetType.OVER:
        return f"{bet.game_id}: o{line}"
    elif bet.bet_type == BetType.UNDER:
        return f"{bet.game_id}: u{line}"
    else:
        sign = "+" if bet.line >= 0 else ""
        return f"{bet.game_id}: {bet.team} {sign}{line}"


@app.route('/')
def index():
    """Serve main page."""
    return render_template('index.html')


# Owner colors matching the spreadsheet
OWNER_COLORS = {
    'Ian': '#f4e4d4',
    'Kevin': '#fff2cc',
    'Torry': '#fce5cd',
    'Daniel': '#f4cccc',
    'Ryan': '#d9ead3',
    'Mitch': '#cfe2f3',
    'David': '#d9d2e9',
    'Nick': '#b6d7a8',
}


@app.route('/api/simulate', methods=['GET'])
def simulate():
    """Run simulation and return complete pre-computed display data."""
    global projections, teams, games

    if not teams or not projections:
        return jsonify({'error': 'Data not loaded'}), 500

    n_sims = request.args.get('n_sims', 10000, type=int)
    n_sims = min(max(n_sims, 1000), 100000)

    try:
        simulator = MonteCarloSimulator(
            teams=teams,
            games=games,
            projections=projections,
            n_sims=n_sims,
        )
        result = simulator.run()

        # Build complete display data
        display_data = build_display_data(result)
        return jsonify(display_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def build_display_data(mc_result):
    """Build complete pre-computed JSON for frontend display."""
    from src.models.bet import BetType
    from src.models.game import GameResult
    from src.scoring.calculator import calculate_fantasy_points, calculate_bet_points

    owners_data = []

    for team in teams:
        owner = team.owner

        # Build player data
        players = []
        player_current_total = 0
        player_projected_total = 0
        minutes_remaining = 0

        for slot in ['qb', 'rb', 'wr', 'te', 'flex']:
            player_name = getattr(team, slot)
            if not player_name:
                players.append({
                    'slot': slot.upper(),
                    'name': None,
                    'team': None,
                    'current_pts': 0,
                    'projected_pts': 0,
                })
                continue

            proj = projections.get(player_name)
            if proj:
                projected = calculate_fantasy_points(proj)

                # Find player's game
                player_game = None
                for g in games.values():
                    if proj.team in [g.away_team, g.home_team]:
                        player_game = g
                        break

                if player_game:
                    remaining_frac = player_game.fraction_remaining
                    current = projected * (1 - remaining_frac)
                    minutes_remaining += int(player_game.time_remaining_seconds / 60)
                else:
                    current = 0

                players.append({
                    'slot': slot.upper(),
                    'name': player_name,
                    'team': proj.team,
                    'current_pts': round(current, 1),
                    'projected_pts': round(projected, 1),
                })
                player_current_total += current
                player_projected_total += projected
            else:
                players.append({
                    'slot': slot.upper(),
                    'name': player_name,
                    'team': None,
                    'current_pts': 0,
                    'projected_pts': 0,
                })

        # Build bet data
        bets = []
        bet_current_total = 0
        bet_projected_total = 0

        for i, bet in enumerate(team.bets):
            bet_id = f'bet{i}'
            mc_data = mc_result.bet_probabilities.get(owner, {}).get(bet_id, {})
            prob = mc_data.get('prob', 0.5)
            expected_pts = mc_data.get('expected_pts', 0)

            # Format bet description
            game_short = bet.game_id.replace(' @ ', '@')
            if bet.bet_type == BetType.OVER:
                description = f"{game_short}: o{bet.adjusted_line}"
            elif bet.bet_type == BetType.UNDER:
                description = f"{game_short}: u{bet.adjusted_line}"
            else:
                sign = '+' if bet.adjusted_line >= 0 else ''
                description = f"{game_short}: {bet.team} {sign}{bet.adjusted_line}"

            # Determine status and current points
            game = games.get(bet.game_id)
            status = 'pending'
            current_pts = 0

            if game and (game.is_final or game.quarter > 0):
                current_total = game.away_score + game.home_score
                current_margin = game.home_score - game.away_score

                if bet.bet_type == BetType.OVER:
                    if current_total > bet.adjusted_line:
                        status = 'winning'
                    elif current_total == bet.adjusted_line:
                        status = 'push'
                    else:
                        status = 'losing'
                elif bet.bet_type == BetType.UNDER:
                    if current_total < bet.adjusted_line:
                        status = 'winning'
                    elif current_total == bet.adjusted_line:
                        status = 'push'
                    else:
                        status = 'losing'
                else:
                    away_team = bet.game_id.split(' @ ')[0]
                    if bet.team == away_team:
                        cover = -current_margin + bet.adjusted_line
                    else:
                        cover = current_margin + bet.adjusted_line
                    if cover > 0:
                        status = 'winning'
                    elif cover == 0:
                        status = 'push'
                    else:
                        status = 'losing'

                if game.is_final:
                    status = 'won' if status == 'winning' else ('push' if status == 'push' else 'lost')
                    # Calculate actual points for resolved bets
                    game_result = GameResult(away_score=game.away_score, home_score=game.home_score)
                    current_pts = calculate_bet_points(bet, game_result)
                    bet_current_total += current_pts

            bets.append({
                'description': description,
                'probability': round(prob, 3),
                'status': status,
                'current_pts': round(current_pts, 1),
                'projected_pts': round(expected_pts, 1),
            })
            bet_projected_total += expected_pts

        # Total = players + bets (both current and projected)
        total_current = player_current_total + bet_current_total
        total_projected = player_projected_total + bet_projected_total

        owners_data.append({
            'name': owner,
            'color': OWNER_COLORS.get(owner, '#cccccc'),
            'win_probability': round(mc_result.win_probabilities.get(owner, 0), 3),
            'current_pts': round(total_current, 1),
            'projected_pts': round(total_projected, 1),
            'minutes_remaining': minutes_remaining,
            'players': players,
            'player_current_total': round(player_current_total, 1),
            'player_projected_total': round(player_projected_total, 1),
            'bets': bets,
        })

    # Sort by win probability descending
    owners_data.sort(key=lambda x: x['win_probability'], reverse=True)

    # Build games data
    games_data = []
    for game_id, game in games.items():
        # Format status
        if game.is_final:
            status = 'Final'
        elif game.quarter == 0:
            status = 'Pre'
        else:
            quarter_seconds = game.time_remaining_seconds % 900
            minutes = quarter_seconds // 60
            seconds = quarter_seconds % 60
            status = f"Q{game.quarter} {minutes}:{seconds:02d}"

        # Format spread
        if game.spread == 0:
            spread_str = 'PK'
        else:
            sign = '+' if game.spread > 0 else ''
            spread_str = f"{sign}{game.spread}"

        games_data.append({
            'matchup': game_id,
            'away_score': game.away_score,
            'home_score': game.home_score,
            'status': status,
            'status_class': 'final' if game.is_final else ('live' if game.quarter > 0 else 'pre'),
            'spread': spread_str,
            'over_under': game.over_under,
        })

    return {
        'owners': owners_data,
        'games': games_data,
        'n_simulations': mc_result.n_simulations,
    }


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Fetch latest live data from ESPN."""
    global games, espn_provider

    if not espn_provider:
        espn_provider = ESPNProvider()

    try:
        games = espn_provider.update_games(games)
        return jsonify({
            'success': True,
            'games': {
                game_id: {
                    'away_team': game.away_team,
                    'home_team': game.home_team,
                    'away_score': game.away_score,
                    'home_score': game.home_score,
                    'quarter': game.quarter,
                    'time_remaining': game.time_remaining_seconds,
                    'is_final': game.is_final,
                }
                for game_id, game in games.items()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scoreboard', methods=['GET'])
def scoreboard():
    """Get current scoreboard state."""
    global games, teams

    return jsonify({
        'games': {
            game_id: {
                'away_team': game.away_team,
                'home_team': game.home_team,
                'away_score': game.away_score,
                'home_score': game.home_score,
                'spread': game.spread,
                'over_under': game.over_under,
                'quarter': game.quarter,
                'time_remaining': game.time_remaining_seconds,
                'is_final': game.is_final,
                'fraction_remaining': game.fraction_remaining,
            }
            for game_id, game in games.items()
        },
        'teams': [
            {
                'owner': team.owner,
                'qb': team.qb,
                'rb': team.rb,
                'wr': team.wr,
                'te': team.te,
                'flex': team.flex,
                'bets': [
                    {
                        'game_id': bet.game_id,
                        'type': bet.bet_type.value,
                        'line': bet.line,
                        'team': bet.team,
                        'adjusted_line': bet.adjusted_line,
                        'draft_round': bet.draft_round,
                    }
                    for bet in team.bets
                ]
            }
            for team in teams
        ] if teams else []
    })


@app.route('/api/update_game', methods=['POST'])
def update_game():
    """Manually update a game's state (for testing or when API is unavailable)."""
    global games

    data = request.json
    game_id = data.get('game_id')

    if game_id not in games:
        return jsonify({'error': f'Game {game_id} not found'}), 404

    game = games[game_id]

    # Update fields if provided
    if 'away_score' in data:
        game.away_score = int(data['away_score'])
    if 'home_score' in data:
        game.home_score = int(data['home_score'])
    if 'quarter' in data:
        game.quarter = int(data['quarter'])
    if 'time_remaining' in data:
        game.time_remaining_seconds = int(data['time_remaining'])

    return jsonify({'success': True, 'game': {
        'game_id': game_id,
        'away_score': game.away_score,
        'home_score': game.home_score,
        'quarter': game.quarter,
        'time_remaining': game.time_remaining_seconds,
    }})


# Initialize on module load
initialize()


if __name__ == '__main__':
    app.run(debug=True, port=5050)
