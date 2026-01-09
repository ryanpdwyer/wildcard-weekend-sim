"""Parse Scoreboard.txt to extract fantasy team rosters and bets."""

import re
from pathlib import Path
from typing import List, Tuple, Optional

from ..models.roster import FantasyTeam
from ..models.bet import Bet, BetType
from ..models.player import Position


# Map of game IDs to (away_team, home_team)
GAMES = {
    "SF @ PHI": ("SF", "PHI"),
    "LAC @ NE": ("LAC", "NE"),
    "BUF @ JAX": ("BUF", "JAX"),
    "GB @ CHI": ("GB", "CHI"),
    "LAR @ CAR": ("LAR", "CAR"),
    "HOU @ PIT": ("HOU", "PIT"),
}


def parse_player_line(line: str) -> Tuple[str, Position, str]:
    """
    Parse a player line like 'Josh Allen, QB, BUF'.

    Returns (name, position, team)
    """
    parts = [p.strip() for p in line.split(',')]
    if len(parts) != 3:
        raise ValueError(f"Invalid player line: {line}")

    name = parts[0]
    pos_str = parts[1]
    team = parts[2]

    position = Position(pos_str)
    return name, position, team


def parse_bet_line(line: str, draft_round: int) -> Bet:
    """
    Parse a bet line like 'SF @ PHI: SF +4.5' or 'GB @ CHI: u45.5'.

    Returns a Bet object.
    """
    # Split on colon
    parts = line.split(':')
    if len(parts) != 2:
        raise ValueError(f"Invalid bet line: {line}")

    game_id = parts[0].strip()
    bet_str = parts[1].strip()

    # Check if it's an O/U or spread
    if bet_str.lower().startswith('o'):
        # Over
        line_val = float(bet_str[1:])
        return Bet(
            game_id=game_id,
            bet_type=BetType.OVER,
            line=line_val,
            team=None,
            draft_round=draft_round,
        )
    elif bet_str.lower().startswith('u'):
        # Under
        line_val = float(bet_str[1:])
        return Bet(
            game_id=game_id,
            bet_type=BetType.UNDER,
            line=line_val,
            team=None,
            draft_round=draft_round,
        )
    else:
        # Spread: "SF +4.5" or "PHI -4.5"
        match = re.match(r'([A-Z]+)\s*([+-]?\d+\.?\d*)', bet_str)
        if not match:
            raise ValueError(f"Invalid spread bet: {bet_str}")

        team = match.group(1)
        line_val = float(match.group(2))

        return Bet(
            game_id=game_id,
            bet_type=BetType.SPREAD,
            line=line_val,
            team=team,
            draft_round=draft_round,
        )


def find_draft_round(player_or_bet: str, draft_data: dict) -> int:
    """
    Look up what round a player or bet was drafted.

    draft_data is a dict mapping player names or bet strings to round numbers.
    """
    return draft_data.get(player_or_bet, 8)


def parse_scoreboard(filepath: str, draft_filepath: str = None) -> List[FantasyTeam]:
    """
    Parse Scoreboard.txt to get all fantasy teams.

    Format detected (starting at line 11):
    - Owner name line (ends with score like '0.00')
    - QB line: 'Name, QB, TEAM'
    - RB line: 'Name, RB, TEAM'
    - WR line: 'Name, WR, TEAM'
    - TE line: 'Name, TE, TEAM'
    - Flex line: 'Name, POS, TEAM'
    - Bet 1: 'GAME: LINE'
    - Bet 2: 'GAME: LINE'
    - Bet 3: 'GAME: LINE'
    - Empty line
    """
    # Parse draft to get round numbers
    draft_rounds = {}
    if draft_filepath:
        draft_rounds = parse_draft_rounds(draft_filepath)

    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Clean lines
    lines = [line.strip() for line in lines]
    # Remove line number prefixes if present (from read output format)
    lines = [re.sub(r'^\d+→', '', line).strip() for line in lines]

    teams = []
    i = 0

    # Skip header lines (first 10 lines are header/summary)
    while i < len(lines) and not _is_owner_line(lines[i]):
        i += 1

    while i < len(lines):
        # Skip empty lines
        if not lines[i]:
            i += 1
            continue

        # Look for owner line
        if _is_owner_line(lines[i]):
            owner = lines[i].split('\t')[0].strip()
            if owner.endswith('0.00'):
                owner = owner[:-4].strip()

            i += 1
            team = FantasyTeam(owner=owner)

            # Parse next 8 lines (5 players + 3 bets)
            player_positions = ['qb', 'rb', 'wr', 'te', 'flex']
            pos_idx = 0
            bets = []

            while i < len(lines) and pos_idx < 5 or len(bets) < 3:
                if not lines[i]:
                    i += 1
                    if i < len(lines) and _is_owner_line(lines[i]):
                        break
                    continue

                line = lines[i]

                # Check if it's a bet line (contains ':' and '@')
                if ':' in line and '@' in line:
                    # Determine draft round from draft data
                    round_num = draft_rounds.get((owner, line), 8)
                    try:
                        bet = parse_bet_line(line, round_num)
                        bets.append(bet)
                    except ValueError as e:
                        print(f"Warning: {e}")
                elif ',' in line:
                    # It's a player line
                    try:
                        name, pos, _ = parse_player_line(line)
                        if pos_idx < len(player_positions):
                            setattr(team, player_positions[pos_idx], name)
                            pos_idx += 1
                    except (ValueError, KeyError) as e:
                        print(f"Warning: {e}")

                i += 1

                # Check if we've moved to a new team
                if i < len(lines) and _is_owner_line(lines[i]):
                    break

            team.bets = bets
            teams.append(team)
        else:
            i += 1

    return teams


def _is_owner_line(line: str) -> bool:
    """Check if a line is an owner name line."""
    # Owner lines end with a score (like 0.00) or are just a name
    # and don't contain commas (players) or @ (bets)
    if not line or ',' in line or '@' in line:
        return False
    # Check if it looks like an owner name
    # Owner names are short and may end with a number
    return bool(re.match(r'^[A-Za-z]+\s*\d*\.?\d*$', line.strip()))


def parse_draft_rounds(filepath: str) -> dict:
    """
    Parse Draft.txt to determine what round each pick was made.

    Returns dict mapping (owner, pick_string) to round number.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Clean lines
    lines = [line.strip() for line in lines]
    lines = [re.sub(r'^\d+→', '', line).strip() for line in lines]

    draft_rounds = {}

    # Parse header to get owner order
    header_line = lines[0] if lines else ""
    owners = []
    if 'Ian' in header_line:  # This is the header with owners
        parts = header_line.split('\t')
        owners = [p.strip() for p in parts if p.strip() and p.strip() not in
                  ['Draft on 1/7/26      at 8:30pm CST', '']]

    current_round = 0
    for line in lines[1:]:
        if line.startswith('Round'):
            current_round = int(line.split()[1])
            # Parse picks on this line (tab-separated)
            parts = line.split('\t')[1:]  # Skip "Round X"
            for col_idx, pick in enumerate(parts):
                if col_idx < len(owners) and pick.strip():
                    owner = owners[col_idx]
                    pick_clean = pick.strip().replace('"', '').replace('\n', ' ')
                    # For players: use player name
                    # For bets: use the full bet string as key
                    draft_rounds[(owner, pick_clean)] = current_round

    return draft_rounds


def parse_scoreboard_simple(filepath: str) -> List[FantasyTeam]:
    """
    Parse Scoreboard.txt to extract fantasy teams.

    The file format has:
    - Lines 1-9: Summary table (header + 8 owner rows with just scores)
    - Line 10: Empty
    - Lines 11+: Detailed team blocks (owner, 5 players, 3 bets per team)
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Clean lines - remove line number prefixes if present
    lines = [re.sub(r'^\s*\d+→', '', line).rstrip('\n\r') for line in lines]

    teams = []
    owner_names = ['Daniel', 'David', 'Ian', 'Kevin', 'Mitch', 'Nick', 'Ryan', 'Torry']

    # Skip to line 11 (index 10) where detailed team data starts
    i = 10

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Check if this is an owner line (starts with owner name, ends with 0.00)
        owner_match = None
        for name in owner_names:
            if line.startswith(name) and '0.00' in line:
                owner_match = name
                break

        if owner_match:
            team = FantasyTeam(owner=owner_match)
            i += 1

            player_slots = []
            bets = []

            # Read next lines until we hit another owner line or end
            while i < len(lines):
                line = lines[i].strip()

                # Skip empty lines within a team block
                if not line:
                    i += 1
                    continue

                # Check if this is the next owner line
                is_next_owner = False
                for name in owner_names:
                    if line.startswith(name) and '0.00' in line:
                        is_next_owner = True
                        break

                if is_next_owner:
                    break

                # Check if it's a bet line (contains '@' and ':')
                if '@' in line and ':' in line:
                    try:
                        bet = parse_bet_line(line, len(bets) + 1)  # Placeholder round
                        bets.append(bet)
                    except ValueError:
                        pass
                # Check if it's a player line (contains commas)
                elif ',' in line:
                    try:
                        name, pos, _ = parse_player_line(line)
                        player_slots.append((name, pos))
                    except (ValueError, KeyError):
                        pass

                i += 1

            # Assign players to roster slots
            for name, pos in player_slots:
                if pos == Position.QB and team.qb is None:
                    team.qb = name
                elif pos == Position.RB and team.rb is None:
                    team.rb = name
                elif pos == Position.WR and team.wr is None:
                    team.wr = name
                elif pos == Position.TE and team.te is None:
                    team.te = name
                elif team.flex is None:
                    team.flex = name

            team.bets = bets
            teams.append(team)
        else:
            i += 1

    return teams
