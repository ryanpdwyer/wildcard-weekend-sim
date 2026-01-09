"""Pytest fixtures for simulation tests."""

import pytest
import numpy as np

from src.models.player import PlayerProjection, PlayerStats, Position
from src.models.game import NFLGame, GameResult
from src.models.bet import Bet, BetType
from src.models.roster import FantasyTeam


@pytest.fixture(autouse=True)
def set_random_seed():
    """Set random seed for reproducible tests."""
    np.random.seed(42)
    yield


@pytest.fixture
def sample_qb_projection():
    """Sample QB projection for testing."""
    return PlayerProjection(
        name="Josh Allen",
        team="BUF",
        position=Position.QB,
        pass_att=30.0,
        pass_cmp=20.0,
        pass_yds=250.0,
        pass_tds=2.0,
        ints=0.5,
        rush_att=6.0,
        rush_yds=35.0,
        rush_tds=0.5,
        fumbles_lost=0.1,
    )


@pytest.fixture
def sample_rb_projection():
    """Sample RB projection for testing."""
    return PlayerProjection(
        name="James Cook III",
        team="BUF",
        position=Position.RB,
        rush_att=18.0,
        rush_yds=94.0,
        rush_tds=0.8,
        rec=2.0,
        rec_yds=16.0,
        rec_tds=0.1,
        fumbles_lost=0.0,
    )


@pytest.fixture
def sample_wr_projection():
    """Sample WR projection for testing."""
    return PlayerProjection(
        name="Puka Nacua",
        team="LAR",
        position=Position.WR,
        rush_att=0.1,
        rush_yds=0.6,
        rush_tds=0.0,
        rec=7.6,
        rec_yds=99.0,
        rec_tds=0.6,
        fumbles_lost=0.0,
    )


@pytest.fixture
def sample_game():
    """Sample NFL game for testing."""
    return NFLGame(
        game_id="BUF @ JAX",
        away_team="BUF",
        home_team="JAX",
        spread=1.5,  # BUF favored by 1.5
        over_under=51.5,
        away_score=14,
        home_score=10,
        time_remaining_seconds=1800,  # Halftime
        quarter=2,
    )


@pytest.fixture
def sample_game_final():
    """Sample completed NFL game."""
    return NFLGame(
        game_id="BUF @ JAX",
        away_team="BUF",
        home_team="JAX",
        spread=1.5,
        over_under=51.5,
        away_score=28,
        home_score=21,
        time_remaining_seconds=0,
        quarter=5,  # Final
    )


@pytest.fixture
def sample_spread_bet():
    """Sample spread bet."""
    return Bet(
        game_id="BUF @ JAX",
        bet_type=BetType.SPREAD,
        line=1.5,  # JAX +1.5
        team="JAX",
        draft_round=3,  # 2.5 point tease
    )


@pytest.fixture
def sample_over_bet():
    """Sample over bet."""
    return Bet(
        game_id="BUF @ JAX",
        bet_type=BetType.OVER,
        line=51.5,
        draft_round=2,  # 6 point tease -> adjusted to 45.5
    )


@pytest.fixture
def sample_under_bet():
    """Sample under bet."""
    return Bet(
        game_id="BUF @ JAX",
        bet_type=BetType.UNDER,
        line=51.5,
        draft_round=4,  # 4 point tease -> adjusted to 55.5
    )


@pytest.fixture
def sample_fantasy_team():
    """Sample fantasy team."""
    return FantasyTeam(
        owner="Test Owner",
        qb="Josh Allen",
        rb="James Cook III",
        wr="Puka Nacua",
        te="Travis Kelce",
        flex="Davante Adams",
        bets=[
            Bet(game_id="BUF @ JAX", bet_type=BetType.SPREAD, line=1.5, team="JAX", draft_round=3),
            Bet(game_id="BUF @ JAX", bet_type=BetType.OVER, line=51.5, draft_round=2),
            Bet(game_id="GB @ CHI", bet_type=BetType.UNDER, line=45.5, draft_round=4),
        ],
    )
