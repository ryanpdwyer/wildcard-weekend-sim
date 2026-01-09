"""ESPN API integration for live NFL game data."""

import requests
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..models.game import NFLGame
from ..models.player import PlayerStats


# ESPN API endpoints
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"


# Team name mapping (ESPN uses different abbreviations sometimes)
ESPN_TEAM_MAP = {
    "JAX": "JAC",  # ESPN uses JAC
    "JAC": "JAX",  # Map back to our format
    "WSH": "WAS",
    "WAS": "WSH",
    "LAR": "LA",
    "LA": "LAR",
}


def normalize_team(team: str) -> str:
    """Normalize team abbreviation."""
    return ESPN_TEAM_MAP.get(team, team)


@dataclass
class ESPNGame:
    """Raw game data from ESPN."""
    event_id: str
    away_team: str
    home_team: str
    away_score: int
    home_score: int
    status: str  # 'pre', 'in', 'post'
    period: int
    clock: str
    time_remaining_seconds: int


class ESPNProvider:
    """Provider for live NFL data from ESPN API."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._game_cache: Dict[str, ESPNGame] = {}

    def get_scoreboard(self) -> List[ESPNGame]:
        """Fetch current NFL scoreboard."""
        try:
            response = requests.get(ESPN_SCOREBOARD_URL, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return self._parse_scoreboard(data)
        except requests.RequestException as e:
            print(f"ESPN API error: {e}")
            return []

    def _parse_scoreboard(self, data: dict) -> List[ESPNGame]:
        """Parse ESPN scoreboard response."""
        games = []

        for event in data.get('events', []):
            try:
                competition = event['competitions'][0]
                competitors = competition['competitors']

                # ESPN lists home first, away second (usually)
                home = next(c for c in competitors if c['homeAway'] == 'home')
                away = next(c for c in competitors if c['homeAway'] == 'away')

                status_detail = competition.get('status', {})
                status_type = status_detail.get('type', {})

                # Parse time remaining
                clock = status_detail.get('displayClock', '0:00')
                period = status_detail.get('period', 0)
                time_remaining = self._calculate_time_remaining(period, clock, status_type.get('state', ''))

                game = ESPNGame(
                    event_id=event['id'],
                    away_team=away['team']['abbreviation'],
                    home_team=home['team']['abbreviation'],
                    away_score=int(away.get('score', 0)),
                    home_score=int(home.get('score', 0)),
                    status=status_type.get('state', 'pre'),
                    period=period,
                    clock=clock,
                    time_remaining_seconds=time_remaining,
                )
                games.append(game)
                self._game_cache[f"{game.away_team} @ {game.home_team}"] = game

            except (KeyError, StopIteration, ValueError) as e:
                print(f"Error parsing game: {e}")
                continue

        return games

    def _calculate_time_remaining(self, period: int, clock: str, status: str) -> int:
        """Calculate total seconds remaining in the game."""
        if status == 'post':
            return 0
        if status == 'pre':
            return 3600  # Full game

        # Parse clock (MM:SS format)
        try:
            parts = clock.split(':')
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                clock_seconds = minutes * 60 + seconds
            else:
                clock_seconds = 0
        except ValueError:
            clock_seconds = 0

        # Calculate remaining time
        # Period 1-4, 15 minutes each
        quarters_remaining = max(0, 4 - period)
        time_in_current_quarter = clock_seconds

        return quarters_remaining * 900 + time_in_current_quarter

    def get_game_state(self, game_id: str) -> Optional[NFLGame]:
        """
        Get current state of a specific game.

        Args:
            game_id: Game identifier like "BUF @ JAX"

        Returns:
            NFLGame with current state, or None if not found
        """
        # Parse game_id
        parts = game_id.split('@')
        if len(parts) != 2:
            return None

        away = parts[0].strip()
        home = parts[1].strip()

        # Refresh scoreboard
        games = self.get_scoreboard()

        # Find matching game
        for espn_game in games:
            espn_away = normalize_team(espn_game.away_team)
            espn_home = normalize_team(espn_game.home_team)

            if (espn_away == away or espn_away == normalize_team(away)) and \
               (espn_home == home or espn_home == normalize_team(home)):
                return NFLGame(
                    game_id=game_id,
                    away_team=away,
                    home_team=home,
                    spread=0.0,  # Will need to be set from betting lines
                    over_under=0.0,
                    away_score=espn_game.away_score,
                    home_score=espn_game.home_score,
                    time_remaining_seconds=espn_game.time_remaining_seconds,
                    quarter=espn_game.period if espn_game.status == 'in' else (5 if espn_game.status == 'post' else 0),
                )

        return None

    def update_games(self, games: Dict[str, NFLGame]) -> Dict[str, NFLGame]:
        """
        Update existing game objects with live data.

        Preserves spread and over_under from original games.

        Args:
            games: Dict of game_id -> NFLGame with betting lines

        Returns:
            Updated games dict
        """
        self.get_scoreboard()  # Refresh cache

        updated = {}
        for game_id, game in games.items():
            live_state = self.get_game_state(game_id)
            if live_state:
                # Update with live data but keep betting lines
                updated[game_id] = NFLGame(
                    game_id=game_id,
                    away_team=game.away_team,
                    home_team=game.home_team,
                    spread=game.spread,
                    over_under=game.over_under,
                    away_score=live_state.away_score,
                    home_score=live_state.home_score,
                    time_remaining_seconds=live_state.time_remaining_seconds,
                    quarter=live_state.quarter,
                )
            else:
                # Keep original game if not found
                updated[game_id] = game

        return updated

    def get_player_stats(self, event_id: str) -> Dict[str, PlayerStats]:
        """
        Get player stats from a game's box score.

        Args:
            event_id: ESPN event ID

        Returns:
            Dict mapping player name to PlayerStats
        """
        try:
            response = requests.get(
                ESPN_SUMMARY_URL,
                params={'event': event_id},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_boxscore(data)
        except requests.RequestException as e:
            print(f"ESPN boxscore API error: {e}")
            return {}

    def _parse_boxscore(self, data: dict) -> Dict[str, PlayerStats]:
        """Parse ESPN boxscore response."""
        stats = {}

        for team_boxscore in data.get('boxscore', {}).get('players', []):
            for stat_group in team_boxscore.get('statistics', []):
                stat_type = stat_group.get('name', '')

                for athlete_data in stat_group.get('athletes', []):
                    athlete = athlete_data.get('athlete', {})
                    player_name = athlete.get('displayName', '')
                    player_stats = athlete_data.get('stats', [])

                    if player_name not in stats:
                        stats[player_name] = PlayerStats()

                    self._update_player_stats(stats[player_name], stat_type, player_stats, stat_group.get('labels', []))

        return stats

    def _update_player_stats(
        self,
        player_stats: PlayerStats,
        stat_type: str,
        values: List[str],
        labels: List[str]
    ):
        """Update player stats from boxscore data."""
        label_map = {label: i for i, label in enumerate(labels)}

        try:
            if stat_type == 'passing':
                # C/ATT, YDS, AVG, TD, INT, SACKS, QBR, RTG
                if 'YDS' in label_map:
                    player_stats.pass_yds = float(values[label_map['YDS']])
                if 'TD' in label_map:
                    player_stats.pass_tds = int(values[label_map['TD']])
                if 'INT' in label_map:
                    player_stats.ints = int(values[label_map['INT']])

            elif stat_type == 'rushing':
                # CAR, YDS, AVG, TD, LONG
                if 'YDS' in label_map:
                    player_stats.rush_yds = float(values[label_map['YDS']])
                if 'TD' in label_map:
                    player_stats.rush_tds = int(values[label_map['TD']])

            elif stat_type == 'receiving':
                # REC, YDS, AVG, TD, LONG, TGTS
                if 'REC' in label_map:
                    player_stats.rec = int(values[label_map['REC']])
                if 'YDS' in label_map:
                    player_stats.rec_yds = float(values[label_map['YDS']])
                if 'TD' in label_map:
                    player_stats.rec_tds = int(values[label_map['TD']])

            elif stat_type == 'fumbles':
                # FUM, LOST, REC
                if 'LOST' in label_map:
                    player_stats.fumbles_lost = int(values[label_map['LOST']])

        except (IndexError, ValueError):
            pass  # Ignore parse errors


def fetch_live_data(games: Dict[str, NFLGame]) -> Dict[str, NFLGame]:
    """
    Convenience function to fetch and update game data.

    Args:
        games: Dict of games with betting lines

    Returns:
        Updated games with live scores
    """
    provider = ESPNProvider()
    return provider.update_games(games)
