"""Simulate player statistics for remaining game time."""

import numpy as np
from typing import Dict

from ..models.player import PlayerProjection, PlayerStats, Position
from ..scoring.calculator import calculate_qb_points, calculate_skill_points
from .distributions import sample_poisson, sample_yards_given_events


# Default variance parameters (can be tuned based on historical data)
YARDS_PER_CARRY_STD = 5.0      # Std dev of yards per carry
YARDS_PER_RECEPTION_STD = 8.0  # Std dev of yards per reception
YARDS_PER_COMPLETION_STD = 6.0  # Std dev of yards per pass completion


class PlayerSimulator:
    """Simulates player stats and fantasy points for remaining game time."""

    def __init__(
        self,
        ypc_std: float = YARDS_PER_CARRY_STD,
        ypr_std: float = YARDS_PER_RECEPTION_STD,
        ypcomp_std: float = YARDS_PER_COMPLETION_STD,
    ):
        self.ypc_std = ypc_std
        self.ypr_std = ypr_std
        self.ypcomp_std = ypcomp_std

    def simulate_remaining(
        self,
        projection: PlayerProjection,
        current_stats: PlayerStats,
        fraction_remaining: float,
        n_sims: int = 10000
    ) -> np.ndarray:
        """
        Simulate remaining stats and return fantasy points array.

        Args:
            projection: Full-game projection for the player
            current_stats: Stats accumulated so far
            fraction_remaining: Fraction of game remaining (0.0 to 1.0)
            n_sims: Number of simulations

        Returns:
            Array of fantasy point totals for each simulation
        """
        if fraction_remaining <= 0:
            # Game is over, just calculate points from current stats
            if projection.position == Position.QB:
                return np.full(n_sims, calculate_qb_points(current_stats))
            else:
                return np.full(n_sims, calculate_skill_points(current_stats))

        # Scale projection by time remaining
        scaled = projection.scale(fraction_remaining)

        if projection.position == Position.QB:
            return self._simulate_qb(scaled, current_stats, n_sims)
        else:
            return self._simulate_skill(scaled, current_stats, n_sims)

    def _simulate_qb(
        self,
        scaled_proj: PlayerProjection,
        current: PlayerStats,
        n_sims: int
    ) -> np.ndarray:
        """Simulate QB stats and return fantasy points."""
        # Sample discrete events from Poisson
        pass_completions = sample_poisson(scaled_proj.pass_cmp, n_sims)
        pass_tds = sample_poisson(scaled_proj.pass_tds, n_sims)
        ints = sample_poisson(scaled_proj.ints, n_sims)
        rush_att = sample_poisson(scaled_proj.rush_att, n_sims)
        rush_tds = sample_poisson(scaled_proj.rush_tds, n_sims)
        fumbles = sample_poisson(scaled_proj.fumbles_lost, n_sims)

        # Sample yards given events
        pass_yds = sample_yards_given_events(
            pass_completions,
            scaled_proj.yards_per_pass_completion,
            self.ypcomp_std
        )
        rush_yds = sample_yards_given_events(
            rush_att,
            scaled_proj.yards_per_rush,
            self.ypc_std
        )

        # Calculate fantasy points for each simulation
        # QB scoring: 1pt/25 pass yds, 4pt pass TD, 6pt rush TD, 1pt/20 rush yds, -2pt turnover
        total_pass_yds = current.pass_yds + pass_yds
        total_pass_tds = current.pass_tds + pass_tds
        total_rush_yds = current.rush_yds + rush_yds
        total_rush_tds = current.rush_tds + rush_tds
        total_ints = current.ints + ints
        total_fumbles = current.fumbles_lost + fumbles

        points = (
            total_pass_yds / 25 +
            total_pass_tds * 4 +
            total_rush_yds / 20 +
            total_rush_tds * 6 +
            (total_ints + total_fumbles) * -2
        )

        return points

    def _simulate_skill(
        self,
        scaled_proj: PlayerProjection,
        current: PlayerStats,
        n_sims: int
    ) -> np.ndarray:
        """Simulate RB/WR/TE stats and return fantasy points."""
        # Sample discrete events from Poisson
        receptions = sample_poisson(scaled_proj.rec, n_sims)
        rec_tds = sample_poisson(scaled_proj.rec_tds, n_sims)
        rush_att = sample_poisson(scaled_proj.rush_att, n_sims)
        rush_tds = sample_poisson(scaled_proj.rush_tds, n_sims)
        fumbles = sample_poisson(scaled_proj.fumbles_lost, n_sims)

        # Sample yards given events
        rec_yds = sample_yards_given_events(
            receptions,
            scaled_proj.yards_per_reception,
            self.ypr_std
        )
        rush_yds = sample_yards_given_events(
            rush_att,
            scaled_proj.yards_per_rush,
            self.ypc_std
        )

        # Calculate fantasy points for each simulation
        # Skill scoring: 0.5 PPR, 1pt/10 yds, 6pt TD, -2pt fumble
        total_rec = current.rec + receptions
        total_rec_yds = current.rec_yds + rec_yds
        total_rec_tds = current.rec_tds + rec_tds
        total_rush_yds = current.rush_yds + rush_yds
        total_rush_tds = current.rush_tds + rush_tds
        total_fumbles = current.fumbles_lost + fumbles

        total_yards = total_rec_yds + total_rush_yds
        total_tds = total_rec_tds + total_rush_tds

        points = (
            total_rec * 0.5 +           # 0.5 PPR
            total_yards / 10 +          # 1pt per 10 yards
            total_tds * 6 +             # 6pt per TD
            total_fumbles * -2          # -2pt per fumble
        )

        return points
