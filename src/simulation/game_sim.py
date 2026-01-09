"""Simulate NFL game scores for remaining game time."""

import numpy as np
from typing import Dict, Tuple

from ..models.game import NFLGame, GameResult
from .distributions import sample_normal


# Historical NFL standard deviation per team per game is roughly 13-14 points
DEFAULT_TEAM_SCORE_STD = 13.5


class GameSimulator:
    """Simulates final game scores based on betting lines and current state."""

    def __init__(self, team_score_std: float = DEFAULT_TEAM_SCORE_STD):
        self.team_score_std = team_score_std

    def simulate_remaining(
        self,
        game: NFLGame,
        n_sims: int = 10000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulate remaining game and return final scores.

        Args:
            game: Current game state with spread, O/U, and current scores
            n_sims: Number of simulations

        Returns:
            Tuple of (away_scores, home_scores) arrays
        """
        if game.is_final:
            # Game is over, return actual scores
            return (
                np.full(n_sims, game.away_score),
                np.full(n_sims, game.home_score)
            )

        # Derive expected final scores from betting lines
        away_exp, home_exp = game.derive_expected_scores()

        # Calculate expected remaining points
        # Use min 5 minutes effective remaining for late-game variance
        frac = max(game.fraction_remaining, 5/60)
        away_remaining_exp = away_exp * frac
        home_remaining_exp = home_exp * frac

        # Variance scales with time remaining (sqrt for standard deviation)
        # Floor of ~5 ensures meaningful late-game variance (can still score TD)
        remaining_std = max(5.0, self.team_score_std * np.sqrt(frac))

        # Sample remaining scores
        away_remaining = sample_normal(away_remaining_exp, remaining_std, n_sims, min_val=0)
        home_remaining = sample_normal(home_remaining_exp, remaining_std, n_sims, min_val=0)

        # Add current scores
        away_final = game.away_score + away_remaining
        home_final = game.home_score + home_remaining

        return away_final, home_final

    def simulate_all_games(
        self,
        games: Dict[str, NFLGame],
        n_sims: int = 10000
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """
        Simulate all games.

        Args:
            games: Dict mapping game_id to NFLGame
            n_sims: Number of simulations

        Returns:
            Dict mapping game_id to (away_scores, home_scores) arrays
        """
        results = {}
        for game_id, game in games.items():
            results[game_id] = self.simulate_remaining(game, n_sims)
        return results
