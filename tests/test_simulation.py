"""Tests for simulation logic."""

import pytest
import numpy as np

from src.models.player import PlayerProjection, PlayerStats, Position
from src.models.game import NFLGame
from src.simulation.player_sim import PlayerSimulator
from src.simulation.game_sim import GameSimulator


class TestPlayerSimulator:
    """Test player stat simulation."""

    def test_qb_simulation_returns_correct_shape(self, sample_qb_projection):
        """QB simulation should return correct number of samples."""
        sim = PlayerSimulator()
        n_sims = 1000
        points = sim.simulate_remaining(
            sample_qb_projection,
            PlayerStats(),
            fraction_remaining=1.0,
            n_sims=n_sims,
        )
        assert points.shape == (n_sims,)

    def test_skill_simulation_returns_correct_shape(self, sample_rb_projection):
        """Skill player simulation should return correct number of samples."""
        sim = PlayerSimulator()
        n_sims = 1000
        points = sim.simulate_remaining(
            sample_rb_projection,
            PlayerStats(),
            fraction_remaining=1.0,
            n_sims=n_sims,
        )
        assert points.shape == (n_sims,)

    def test_simulation_with_time_remaining_zero(self, sample_qb_projection):
        """When game is over, should return deterministic points."""
        sim = PlayerSimulator()
        current_stats = PlayerStats(pass_yds=200, pass_tds=2)
        points = sim.simulate_remaining(
            sample_qb_projection,
            current_stats,
            fraction_remaining=0.0,
            n_sims=100,
        )
        # All values should be identical (deterministic)
        assert np.all(points == points[0])

    def test_simulation_mean_scales_with_projection(self, sample_rb_projection):
        """Expected points should roughly match projection."""
        sim = PlayerSimulator()
        np.random.seed(42)

        # Full game simulation
        points = sim.simulate_remaining(
            sample_rb_projection,
            PlayerStats(),
            fraction_remaining=1.0,
            n_sims=10000,
        )

        # Expected points from projection (manual calculation)
        # rush_yds=94, rush_tds=0.8, rec=2, rec_yds=16, rec_tds=0.1
        # Points = 94/10 + 0.8*6 + 2*0.5 + 16/10 + 0.1*6
        # Points = 9.4 + 4.8 + 1.0 + 1.6 + 0.6 = 17.4
        # But with variance, mean should be close to this
        assert abs(points.mean() - 17.0) < 2.0  # Within 2 points

    def test_simulation_half_time_reduces_variance(self, sample_rb_projection):
        """Half time remaining should have less variance than full game."""
        sim = PlayerSimulator()
        np.random.seed(42)

        full_game = sim.simulate_remaining(
            sample_rb_projection,
            PlayerStats(),
            fraction_remaining=1.0,
            n_sims=10000,
        )

        np.random.seed(42)
        half_game = sim.simulate_remaining(
            sample_rb_projection,
            PlayerStats(),
            fraction_remaining=0.5,
            n_sims=10000,
        )

        # Half game should have less variance
        assert half_game.std() < full_game.std()

    def test_simulation_adds_current_stats(self, sample_rb_projection):
        """Current stats should be added to simulated remaining."""
        sim = PlayerSimulator()
        np.random.seed(42)

        # With current stats of 50 yards rushing
        current = PlayerStats(rush_yds=50, rec=1)
        points_with_current = sim.simulate_remaining(
            sample_rb_projection,
            current,
            fraction_remaining=0.5,
            n_sims=10000,
        )

        np.random.seed(42)
        # Without current stats
        points_without = sim.simulate_remaining(
            sample_rb_projection,
            PlayerStats(),
            fraction_remaining=0.5,
            n_sims=10000,
        )

        # With current stats should average higher
        # 50 yards = 5 pts, 1 rec = 0.5 pts = 5.5 pts more
        diff = points_with_current.mean() - points_without.mean()
        assert abs(diff - 5.5) < 1.0


class TestGameSimulator:
    """Test game score simulation."""

    def test_game_simulation_returns_correct_shape(self, sample_game):
        """Game simulation should return correct number of samples."""
        sim = GameSimulator()
        n_sims = 1000
        away, home = sim.simulate_remaining(sample_game, n_sims)
        assert away.shape == (n_sims,)
        assert home.shape == (n_sims,)

    def test_final_game_returns_actual_scores(self, sample_game_final):
        """Final game should return actual scores."""
        sim = GameSimulator()
        n_sims = 100
        away, home = sim.simulate_remaining(sample_game_final, n_sims)

        # All values should equal actual scores
        assert np.all(away == 28)
        assert np.all(home == 21)

    def test_game_scores_non_negative(self, sample_game):
        """Game scores should not be negative."""
        sim = GameSimulator()
        np.random.seed(42)
        away, home = sim.simulate_remaining(sample_game, 10000)

        # Current scores are 14-10, remaining should not make total negative
        assert np.all(away >= 14)  # At least current score
        assert np.all(home >= 10)

    def test_expected_scores_from_lines(self):
        """Test that expected scores are derived correctly from lines."""
        game = NFLGame(
            game_id="TEST",
            away_team="A",
            home_team="H",
            spread=-7.0,  # Home favored by 7
            over_under=50.0,
        )

        away_exp, home_exp = game.derive_expected_scores()

        # O/U = away + home = 50
        # spread = home - away = -7 (home scores 7 more)
        # Solving: home = (50 - (-7)) / 2 = 28.5
        #          away = (50 + (-7)) / 2 = 21.5
        assert away_exp == 21.5
        assert home_exp == 28.5

    def test_simulation_mean_matches_expected(self, sample_game):
        """Simulated mean should be close to derived expected."""
        sim = GameSimulator()
        np.random.seed(42)

        # Game at halftime with 14-10 score
        away, home = sim.simulate_remaining(sample_game, 100000)

        # Expected final scores
        away_exp, home_exp = sample_game.derive_expected_scores()

        # Current + expected remaining ≈ simulated mean
        # Half game remaining, so expected remaining = expected_final * 0.5
        expected_away_final = 14 + (away_exp * 0.5)
        expected_home_final = 10 + (home_exp * 0.5)

        assert abs(away.mean() - expected_away_final) < 1.0
        assert abs(home.mean() - expected_home_final) < 1.0


class TestGameProperties:
    """Test NFLGame property calculations."""

    def test_fraction_remaining_full(self):
        """Full game should have fraction 1.0."""
        game = NFLGame(
            game_id="TEST", away_team="A", home_team="H",
            spread=0, over_under=50,
            time_remaining_seconds=3600,
        )
        assert game.fraction_remaining == 1.0

    def test_fraction_remaining_half(self):
        """Halftime should have fraction 0.5."""
        game = NFLGame(
            game_id="TEST", away_team="A", home_team="H",
            spread=0, over_under=50,
            time_remaining_seconds=1800,
        )
        assert game.fraction_remaining == 0.5

    def test_fraction_remaining_final(self):
        """Final game should have fraction 0.0."""
        game = NFLGame(
            game_id="TEST", away_team="A", home_team="H",
            spread=0, over_under=50,
            time_remaining_seconds=0,
            quarter=5,
        )
        assert game.fraction_remaining == 0.0

    def test_is_final_by_quarter(self):
        """Quarter 5 indicates final."""
        game = NFLGame(
            game_id="TEST", away_team="A", home_team="H",
            spread=0, over_under=50,
            quarter=5,
        )
        assert game.is_final

    def test_is_final_by_time(self):
        """Q4 with 0 time remaining is final."""
        game = NFLGame(
            game_id="TEST", away_team="A", home_team="H",
            spread=0, over_under=50,
            quarter=4,
            time_remaining_seconds=0,
        )
        assert game.is_final
