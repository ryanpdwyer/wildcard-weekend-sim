"""Main Monte Carlo simulation orchestrator."""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from ..models.player import PlayerProjection, PlayerStats, Position
from ..models.game import NFLGame, GameResult
from ..models.bet import Bet, BetType
from ..models.roster import FantasyTeam
from ..scoring.calculator import calculate_bet_points, _parse_game_teams
from .player_sim import PlayerSimulator
from .game_sim import GameSimulator


@dataclass
class SimulationResult:
    """Results from a Monte Carlo simulation run."""
    win_probabilities: Dict[str, float]
    expected_scores: Dict[str, float]
    score_std: Dict[str, float]
    n_simulations: int
    bet_probabilities: Dict[str, Dict[str, float]] = None  # owner -> bet_id -> prob
    player_expected_points: Dict[str, float] = None  # player_name -> expected points

    def to_dict(self) -> dict:
        return {
            'win_probabilities': self.win_probabilities,
            'expected_scores': self.expected_scores,
            'score_std': self.score_std,
            'n_simulations': self.n_simulations,
            'bet_probabilities': self.bet_probabilities,
            'player_expected_points': self.player_expected_points,
        }


class MonteCarloSimulator:
    """Main simulation orchestrator for win probability calculation."""

    def __init__(
        self,
        teams: List[FantasyTeam],
        games: Dict[str, NFLGame],
        projections: Dict[str, PlayerProjection],
        current_stats: Optional[Dict[str, PlayerStats]] = None,
        n_sims: int = 10000
    ):
        """
        Initialize the simulator.

        Args:
            teams: List of fantasy teams with rosters and bets
            games: Dict of NFL games by game_id (e.g., "SF @ PHI")
            projections: Dict of player projections by player name
            current_stats: Dict of current player stats by player name (optional)
            n_sims: Number of simulations to run
        """
        self.teams = teams
        self.games = games
        self.projections = projections
        self.current_stats = current_stats or {}
        self.n_sims = n_sims

        self.player_sim = PlayerSimulator()
        self.game_sim = GameSimulator()

    def run(self) -> SimulationResult:
        """
        Run Monte Carlo simulation.

        Returns:
            SimulationResult with win probabilities and expected scores
        """
        # 1. Simulate all game final scores
        game_results = self.game_sim.simulate_all_games(self.games, self.n_sims)

        # 2. Calculate fantasy points for each team in each simulation
        n_teams = len(self.teams)
        team_scores = np.zeros((n_teams, self.n_sims))
        bet_win_counts = {}  # owner -> bet_id -> win_count
        player_points = {}  # player_name -> expected points

        for i, team in enumerate(self.teams):
            # Add player points
            for player_name in team.all_player_names:
                points = self._simulate_player_points(player_name)
                team_scores[i] += points
                player_points[player_name] = float(np.mean(points))

            # Add bet points and track wins + expected points
            bet_win_counts[team.owner] = {}
            for j, bet in enumerate(team.bets):
                if bet.game_id in game_results:
                    away_scores, home_scores = game_results[bet.game_id]
                    bet_points = self._calculate_bet_points_array(bet, away_scores, home_scores)
                    team_scores[i] += bet_points
                    # Track wins and expected points
                    bet_win_counts[team.owner][f'bet{j}'] = {
                        'wins': int(np.sum(bet_points > 0)),
                        'expected_pts': float(np.mean(bet_points)),
                    }

        # 3. Determine winner for each simulation
        winners = np.argmax(team_scores, axis=0)

        # 4. Calculate statistics
        win_counts = np.bincount(winners, minlength=n_teams)
        win_probs = win_counts / self.n_sims

        expected_scores = np.mean(team_scores, axis=1)
        score_stds = np.std(team_scores, axis=1)

        # 5. Calculate bet probabilities and expected points from simulation
        bet_probs = {}
        for owner, bets in bet_win_counts.items():
            bet_probs[owner] = {
                bet_id: {
                    'prob': data['wins'] / self.n_sims,
                    'expected_pts': data['expected_pts'],
                }
                for bet_id, data in bets.items()
            }

        return SimulationResult(
            win_probabilities={team.owner: float(prob) for team, prob in zip(self.teams, win_probs)},
            expected_scores={team.owner: float(score) for team, score in zip(self.teams, expected_scores)},
            score_std={team.owner: float(std) for team, std in zip(self.teams, score_stds)},
            n_simulations=self.n_sims,
            bet_probabilities=bet_probs,
            player_expected_points=player_points,
        )

    def _simulate_player_points(self, player_name: str) -> np.ndarray:
        """Simulate fantasy points for a player."""
        if player_name not in self.projections:
            # Player not found in projections, return zeros
            print(f"Warning: No projection found for {player_name}")
            return np.zeros(self.n_sims)

        proj = self.projections[player_name]
        current = self.current_stats.get(player_name, PlayerStats())

        # Find the game this player is in
        game = self._find_player_game(proj.team)
        if game is None:
            print(f"Warning: No game found for {player_name} (team {proj.team})")
            return np.zeros(self.n_sims)

        return self.player_sim.simulate_remaining(
            proj, current, game.fraction_remaining, self.n_sims
        )

    def _find_player_game(self, team: str) -> Optional[NFLGame]:
        """Find the game that a team is playing in."""
        for game in self.games.values():
            if game.away_team == team or game.home_team == team:
                return game
        return None

    def _calculate_bet_points_array(
        self,
        bet: Bet,
        away_scores: np.ndarray,
        home_scores: np.ndarray
    ) -> np.ndarray:
        """
        Calculate bet points for each simulation.

        Vectorized version of calculate_bet_points.
        """
        if bet.bet_type == BetType.OVER:
            total = away_scores + home_scores
            margin = total - bet.adjusted_line
            won = margin > 0
            bonus = np.minimum(10, np.maximum(0, margin))
            return won * (10 + bonus)

        elif bet.bet_type == BetType.UNDER:
            total = away_scores + home_scores
            margin = bet.adjusted_line - total
            won = margin > 0
            bonus = np.minimum(10, np.maximum(0, margin * 2))
            return won * (10 + bonus)

        else:  # SPREAD
            away_team, home_team = _parse_game_teams(bet.game_id)

            if bet.team == away_team:
                actual_margin = away_scores - home_scores
            else:  # bet on home team
                actual_margin = home_scores - away_scores

            cover_margin = actual_margin + bet.adjusted_line
            won = cover_margin > 0
            push = cover_margin == 0
            bonus = np.minimum(10, np.maximum(0, cover_margin))

            # Won bets get base + bonus, pushes get 0, losses get 0
            return won * (10 + bonus) + push * 0


def create_default_games() -> Dict[str, NFLGame]:
    """
    Create the 6 wildcard weekend games with default betting lines.

    These should be updated with actual lines before running.
    """
    return {
        "LAR @ CAR": NFLGame(
            game_id="LAR @ CAR",
            away_team="LAR",
            home_team="CAR",
            spread=10.5,  # LAR favored by 10.5
            over_under=46.5,
            start_time="Sat 4:30 PM",
        ),
        "GB @ CHI": NFLGame(
            game_id="GB @ CHI",
            away_team="GB",
            home_team="CHI",
            spread=1.5,  # GB favored by 1.5
            over_under=45.5,
            start_time="Sat 8:00 PM",
        ),
        "BUF @ JAX": NFLGame(
            game_id="BUF @ JAX",
            away_team="BUF",
            home_team="JAX",
            spread=1.5,  # BUF favored by 1.5 (positive = home underdog)
            over_under=51.5,
            start_time="Sun 1:00 PM",
        ),
        "SF @ PHI": NFLGame(
            game_id="SF @ PHI",
            away_team="SF",
            home_team="PHI",
            spread=-4.5,  # PHI favored by 4.5
            over_under=44.5,
            start_time="Sun 4:30 PM",
        ),
        "LAC @ NE": NFLGame(
            game_id="LAC @ NE",
            away_team="LAC",
            home_team="NE",
            spread=-3.5,  # NE favored by 3.5 (negative = home favored)
            over_under=46.5,
            start_time="Sun 8:00 PM",
        ),
        "HOU @ PIT": NFLGame(
            game_id="HOU @ PIT",
            away_team="HOU",
            home_team="PIT",
            spread=3.0,  # HOU favored by 3 (positive = away favored, PIT +3 underdog)
            over_under=39.5,
            start_time="Mon 8:00 PM",
        ),
    }
