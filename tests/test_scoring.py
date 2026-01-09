"""Tests for scoring calculation."""

import pytest
from src.models.player import PlayerStats, Position
from src.models.game import GameResult
from src.models.bet import Bet, BetType
from src.scoring.calculator import (
    calculate_qb_points,
    calculate_skill_points,
    calculate_spread_points,
    calculate_ou_points,
)


class TestQBScoring:
    """Test QB fantasy point calculations."""

    def test_basic_qb_scoring(self):
        """Test basic QB scoring with all stat categories."""
        stats = PlayerStats(
            pass_yds=250,   # 250/25 = 10 points
            pass_tds=2,     # 2 * 4 = 8 points
            rush_yds=40,    # 40/20 = 2 points
            rush_tds=1,     # 1 * 6 = 6 points
            ints=1,         # 1 * -2 = -2 points
            fumbles_lost=0,
        )
        # Total: 10 + 8 + 2 + 6 - 2 = 24
        assert calculate_qb_points(stats) == 24.0

    def test_qb_turnover_penalty(self):
        """Test that both INTs and fumbles count as turnovers."""
        stats = PlayerStats(
            pass_yds=0,
            pass_tds=0,
            rush_yds=0,
            rush_tds=0,
            ints=2,
            fumbles_lost=1,
        )
        # Total: -2 * 3 = -6
        assert calculate_qb_points(stats) == -6.0

    def test_qb_zero_stats(self):
        """Test QB with zero stats."""
        stats = PlayerStats()
        assert calculate_qb_points(stats) == 0.0

    def test_qb_fractional_yards(self):
        """Test QB with fractional yards."""
        stats = PlayerStats(
            pass_yds=100,  # 100/25 = 4 points
        )
        assert calculate_qb_points(stats) == 4.0


class TestSkillScoring:
    """Test RB/WR/TE fantasy point calculations."""

    def test_basic_rb_scoring(self):
        """Test RB scoring with all stat categories."""
        stats = PlayerStats(
            rush_yds=100,   # 100/10 = 10 points
            rush_tds=1,     # 1 * 6 = 6 points
            rec=5,          # 5 * 0.5 = 2.5 points (PPR)
            rec_yds=50,     # 50/10 = 5 points
            rec_tds=0,
            fumbles_lost=1, # 1 * -2 = -2 points
        )
        # Total: 10 + 6 + 2.5 + 5 - 2 = 21.5
        assert calculate_skill_points(stats) == 21.5

    def test_wr_ppr_scoring(self):
        """Test WR with PPR emphasis."""
        stats = PlayerStats(
            rec=8,          # 8 * 0.5 = 4 points (PPR)
            rec_yds=120,    # 120/10 = 12 points
            rec_tds=1,      # 1 * 6 = 6 points
        )
        # Total: 4 + 12 + 6 = 22
        assert calculate_skill_points(stats) == 22.0

    def test_skill_zero_stats(self):
        """Test skill player with zero stats."""
        stats = PlayerStats()
        assert calculate_skill_points(stats) == 0.0


class TestSpreadScoring:
    """Test spread bet scoring."""

    def test_spread_win_with_bonus(self):
        """Test spread bet that wins and covers by extra points."""
        # JAX +4.0 adjusted (1.5 + 2.5 tease)
        # BUF wins 28-21, JAX loses by 7
        # Cover margin = -7 + 4.0 = -3 (lost)
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=1.5,
            team="JAX",
            draft_round=3,  # 2.5 tease
        )
        result = GameResult(away_score=28, home_score=21)
        # JAX at +4.0 loses by 7, doesn't cover
        assert calculate_spread_points(bet, result) == 0.0

    def test_spread_win_favorite(self):
        """Test betting on favorite that covers."""
        # BUF -1.5, tease of 2.5 -> adjusted -1.5 + 2.5 = +1.0 (wait, this is wrong)
        # For the favorite side, the line is negative
        # Let's test: LAR -10.5 with 2.5 tease -> -8.0
        bet = Bet(
            game_id="LAR @ CAR",
            bet_type=BetType.SPREAD,
            line=-10.5,  # LAR favored by 10.5
            team="LAR",
            draft_round=3,  # 2.5 tease -> -8.0
        )
        # LAR wins 35-14, margin = 21
        result = GameResult(away_score=35, home_score=14)
        # Cover margin = 21 + (-8.0) = 13
        # Points = 10 + min(10, 13) = 20
        assert calculate_spread_points(bet, result) == 20.0

    def test_spread_push(self):
        """Test spread push (no points)."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=7.0,  # No tease for simplicity
            team="JAX",
            draft_round=8,  # 0 tease
        )
        # BUF wins 28-21, JAX loses by exactly 7
        result = GameResult(away_score=28, home_score=21)
        # Cover margin = -7 + 7 = 0 (push)
        assert calculate_spread_points(bet, result) == 0.0

    def test_spread_loss(self):
        """Test spread loss."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=3.0,
            team="JAX",
            draft_round=8,
        )
        # BUF wins 28-21, JAX loses by 7
        result = GameResult(away_score=28, home_score=21)
        # Cover margin = -7 + 3 = -4 (lost)
        assert calculate_spread_points(bet, result) == 0.0


class TestOUScoring:
    """Test over/under bet scoring."""

    def test_over_win_with_bonus(self):
        """Test over bet that wins with bonus."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=51.5,
            draft_round=2,  # 6 point tease -> 45.5
        )
        # Total score = 49
        result = GameResult(away_score=28, home_score=21)
        # Margin = 49 - 45.5 = 3.5
        # Points = 10 + min(10, 3.5) = 13.5
        assert calculate_ou_points(bet, result) == 13.5

    def test_under_win_with_bonus(self):
        """Test under bet with 2x bonus."""
        bet = Bet(
            game_id="HOU @ PIT",
            bet_type=BetType.UNDER,
            line=39.5,
            draft_round=4,  # 4 point tease -> 43.5
        )
        # Total score = 35
        result = GameResult(away_score=21, home_score=14)
        # Margin = 43.5 - 35 = 8.5
        # Bonus = min(10, 8.5 * 2) = 10 (capped)
        # Points = 10 + 10 = 20
        assert calculate_ou_points(bet, result) == 20.0

    def test_over_loss(self):
        """Test over bet loss."""
        bet = Bet(
            game_id="HOU @ PIT",
            bet_type=BetType.OVER,
            line=39.5,
            draft_round=8,  # 0 tease
        )
        # Total score = 35
        result = GameResult(away_score=21, home_score=14)
        assert calculate_ou_points(bet, result) == 0.0

    def test_ou_push(self):
        """Test O/U push."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=49.0,
            draft_round=8,
        )
        result = GameResult(away_score=28, home_score=21)
        # Margin = 49 - 49 = 0 (push)
        assert calculate_ou_points(bet, result) == 0.0


class TestTeaseBonus:
    """Test tease bonus calculations."""

    def test_spread_tease_by_round(self):
        """Test spread tease bonus decreases by round."""
        expected_teases = {1: 3.5, 2: 3.0, 3: 2.5, 4: 2.0, 5: 1.5, 6: 1.0, 7: 0.5, 8: 0.0}
        for round_num, expected in expected_teases.items():
            bet = Bet(
                game_id="X @ Y",
                bet_type=BetType.SPREAD,
                line=0,
                team="X",
                draft_round=round_num,
            )
            assert bet.tease_bonus == expected, f"Round {round_num}"

    def test_ou_tease_by_round(self):
        """Test O/U tease bonus decreases by round."""
        expected_teases = {1: 7.0, 2: 6.0, 3: 5.0, 4: 4.0, 5: 3.0, 6: 2.0, 7: 1.0, 8: 0.0}
        for round_num, expected in expected_teases.items():
            bet = Bet(
                game_id="X @ Y",
                bet_type=BetType.OVER,
                line=50,
                draft_round=round_num,
            )
            assert bet.tease_bonus == expected, f"Round {round_num}"

    def test_adjusted_line_spread(self):
        """Test adjusted line for spread bet."""
        bet = Bet(
            game_id="X @ Y",
            bet_type=BetType.SPREAD,
            line=3.0,  # Underdog getting 3 points
            team="Y",
            draft_round=1,  # 3.5 tease
        )
        # Adjusted = 3.0 + 3.5 = 6.5
        assert bet.adjusted_line == 6.5

    def test_adjusted_line_over(self):
        """Test adjusted line for over bet."""
        bet = Bet(
            game_id="X @ Y",
            bet_type=BetType.OVER,
            line=50.0,
            draft_round=1,  # 7 tease
        )
        # Adjusted = 50.0 - 7 = 43.0 (lower bar)
        assert bet.adjusted_line == 43.0

    def test_adjusted_line_under(self):
        """Test adjusted line for under bet."""
        bet = Bet(
            game_id="X @ Y",
            bet_type=BetType.UNDER,
            line=50.0,
            draft_round=1,  # 7 tease
        )
        # Adjusted = 50.0 + 7 = 57.0 (higher ceiling)
        assert bet.adjusted_line == 57.0
