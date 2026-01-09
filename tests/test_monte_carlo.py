"""Tests for Monte Carlo simulation."""

import pytest
import numpy as np

from src.models.player import PlayerProjection, PlayerStats, Position
from src.models.game import NFLGame
from src.models.bet import Bet, BetType
from src.models.roster import FantasyTeam
from src.simulation.monte_carlo import MonteCarloSimulator, create_default_games


class TestMonteCarloSimulator:
    """Test Monte Carlo simulation."""

    @pytest.fixture
    def simple_teams(self):
        """Create simple test teams."""
        return [
            FantasyTeam(
                owner="Team1",
                qb="Josh Allen",
                rb="James Cook III",
                wr="Puka Nacua",
                te="Travis Kelce",
                flex="Davante Adams",
                bets=[
                    Bet(game_id="BUF @ JAX", bet_type=BetType.OVER, line=51.5, draft_round=2),
                ],
            ),
            FantasyTeam(
                owner="Team2",
                qb="Matthew Stafford",
                rb="Christian McCaffrey",
                wr="A.J. Brown",
                te="George Kittle",
                flex="Kyren Williams",
                bets=[
                    Bet(game_id="SF @ PHI", bet_type=BetType.UNDER, line=44.5, draft_round=3),
                ],
            ),
        ]

    @pytest.fixture
    def simple_projections(self):
        """Create simple test projections."""
        return {
            "Josh Allen": PlayerProjection(
                name="Josh Allen", team="BUF", position=Position.QB,
                pass_att=30, pass_cmp=20, pass_yds=250, pass_tds=2, ints=0.5,
                rush_att=6, rush_yds=35, rush_tds=0.5,
            ),
            "James Cook III": PlayerProjection(
                name="James Cook III", team="BUF", position=Position.RB,
                rush_att=18, rush_yds=94, rush_tds=0.8, rec=2, rec_yds=16, rec_tds=0.1,
            ),
            "Puka Nacua": PlayerProjection(
                name="Puka Nacua", team="LAR", position=Position.WR,
                rec=7.6, rec_yds=99, rec_tds=0.6,
            ),
            "Travis Kelce": PlayerProjection(
                name="Travis Kelce", team="KC", position=Position.TE,
                rec=5, rec_yds=50, rec_tds=0.4,
            ),
            "Davante Adams": PlayerProjection(
                name="Davante Adams", team="LAR", position=Position.WR,
                rec=4, rec_yds=57, rec_tds=0.7,
            ),
            "Matthew Stafford": PlayerProjection(
                name="Matthew Stafford", team="LAR", position=Position.QB,
                pass_att=35, pass_cmp=23, pass_yds=275, pass_tds=2.1, ints=0.6,
                rush_att=1, rush_yds=4, rush_tds=0,
            ),
            "Christian McCaffrey": PlayerProjection(
                name="Christian McCaffrey", team="SF", position=Position.RB,
                rush_att=17, rush_yds=71, rush_tds=0.5, rec=5, rec_yds=43, rec_tds=0.3,
            ),
            "A.J. Brown": PlayerProjection(
                name="A.J. Brown", team="PHI", position=Position.WR,
                rec=6, rec_yds=70, rec_tds=0.6,
            ),
            "George Kittle": PlayerProjection(
                name="George Kittle", team="SF", position=Position.TE,
                rec=5, rec_yds=60, rec_tds=0.4,
            ),
            "Kyren Williams": PlayerProjection(
                name="Kyren Williams", team="LAR", position=Position.RB,
                rush_att=16, rush_yds=71, rush_tds=0.6, rec=2, rec_yds=12, rec_tds=0.1,
            ),
        }

    @pytest.fixture
    def simple_games(self):
        """Create simple test games."""
        return {
            "BUF @ JAX": NFLGame(
                game_id="BUF @ JAX", away_team="BUF", home_team="JAX",
                spread=1.5, over_under=51.5,
            ),
            "SF @ PHI": NFLGame(
                game_id="SF @ PHI", away_team="SF", home_team="PHI",
                spread=-4.5, over_under=44.5,
            ),
            "LAR @ CAR": NFLGame(
                game_id="LAR @ CAR", away_team="LAR", home_team="CAR",
                spread=10.5, over_under=46.5,
            ),
        }

    def test_simulation_returns_result(self, simple_teams, simple_projections, simple_games):
        """Simulation should return a SimulationResult."""
        sim = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=1000,
        )
        result = sim.run()

        assert hasattr(result, 'win_probabilities')
        assert hasattr(result, 'expected_scores')
        assert hasattr(result, 'n_simulations')

    def test_probabilities_sum_to_one(self, simple_teams, simple_projections, simple_games):
        """Win probabilities should sum to approximately 1.0."""
        sim = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=10000,
        )
        result = sim.run()

        total_prob = sum(result.win_probabilities.values())
        assert abs(total_prob - 1.0) < 0.001

    def test_probabilities_non_negative(self, simple_teams, simple_projections, simple_games):
        """All probabilities should be non-negative."""
        sim = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=1000,
        )
        result = sim.run()

        for prob in result.win_probabilities.values():
            assert prob >= 0.0

    def test_simulation_reproducible_with_seed(self, simple_teams, simple_projections, simple_games):
        """Results should be reproducible with same seed."""
        np.random.seed(42)
        sim1 = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=1000,
        )
        result1 = sim1.run()

        np.random.seed(42)
        sim2 = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=1000,
        )
        result2 = sim2.run()

        for owner in result1.win_probabilities:
            assert result1.win_probabilities[owner] == result2.win_probabilities[owner]

    def test_expected_scores_reasonable(self, simple_teams, simple_projections, simple_games):
        """Expected scores should be in reasonable range."""
        sim = MonteCarloSimulator(
            teams=simple_teams,
            games=simple_games,
            projections=simple_projections,
            n_sims=5000,
        )
        result = sim.run()

        for owner, score in result.expected_scores.items():
            # Fantasy scores typically range from ~50 to ~200
            assert 30 < score < 300, f"Unreasonable score for {owner}: {score}"


class TestBetPointsArray:
    """Test vectorized bet points calculation in Monte Carlo."""

    @pytest.fixture
    def simulator(self):
        """Create a minimal simulator for testing bet scoring."""
        games = {
            "BUF @ JAX": NFLGame(
                game_id="BUF @ JAX", away_team="BUF", home_team="JAX",
                spread=1.5, over_under=51.5,
            ),
        }
        return MonteCarloSimulator(
            teams=[],
            games=games,
            projections={},
            n_sims=1,
        )

    def test_over_bet_wins_when_total_exceeds_line(self, simulator):
        """Over bet wins when away + home > adjusted_line."""
        # BUF 28, JAX 21 -> total = 49
        # Over 45.5 adjusted -> margin = 3.5 -> wins
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=51.5,
            draft_round=2,  # 6 point tease -> adjusted 45.5
        )
        away_scores = np.array([28.0])
        home_scores = np.array([21.0])

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # Margin = 49 - 45.5 = 3.5, bonus = 3.5
        # Points = 10 + 3.5 = 13.5
        assert points[0] == pytest.approx(13.5, rel=0.01)

    def test_over_bet_loses_when_total_below_line(self, simulator):
        """Over bet loses when away + home < adjusted_line."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=51.5,
            draft_round=8,  # No tease -> adjusted 51.5
        )
        away_scores = np.array([21.0])
        home_scores = np.array([20.0])  # total = 41

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)
        assert points[0] == 0.0

    def test_under_bet_wins_when_total_below_line(self, simulator):
        """Under bet wins when away + home < adjusted_line."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.UNDER,
            line=39.5,
            draft_round=4,  # 4 point tease -> adjusted 43.5
        )
        away_scores = np.array([17.0])
        home_scores = np.array([14.0])  # total = 31

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # Margin = 43.5 - 31 = 12.5, bonus = min(10, 12.5*2) = 10
        # Points = 10 + 10 = 20
        assert points[0] == 20.0

    def test_under_bet_loses_when_total_above_line(self, simulator):
        """Under bet loses when away + home > adjusted_line."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.UNDER,
            line=39.5,
            draft_round=8,  # No tease -> 39.5
        )
        away_scores = np.array([28.0])
        home_scores = np.array([21.0])  # total = 49

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)
        assert points[0] == 0.0

    def test_spread_away_team_covers(self, simulator):
        """Spread bet on away team wins when they cover."""
        # BUF @ JAX, betting BUF -1.5 with 2.5 tease -> +1.0
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=-1.5,  # BUF favored
            team="BUF",
            draft_round=3,  # 2.5 tease -> adjusted +1.0
        )
        away_scores = np.array([28.0])  # BUF
        home_scores = np.array([21.0])  # JAX

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # BUF margin = 28 - 21 = 7
        # Cover margin = 7 + 1.0 = 8
        # Points = 10 + min(10, 8) = 18
        assert points[0] == 18.0

    def test_spread_home_team_covers(self, simulator):
        """Spread bet on home team wins when they cover."""
        # JAX +1.5 with 2.5 tease -> +4.0
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=1.5,  # JAX underdog
            team="JAX",
            draft_round=3,  # 2.5 tease -> adjusted 4.0
        )
        away_scores = np.array([24.0])  # BUF
        home_scores = np.array([21.0])  # JAX

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # JAX margin = 21 - 24 = -3
        # Cover margin = -3 + 4.0 = 1
        # Points = 10 + min(10, 1) = 11
        assert points[0] == 11.0

    def test_spread_does_not_cover(self, simulator):
        """Spread bet loses when team doesn't cover."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=1.5,  # JAX +1.5
            team="JAX",
            draft_round=8,  # No tease -> 1.5
        )
        away_scores = np.array([28.0])
        home_scores = np.array([21.0])  # loses by 7

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # JAX margin = 21 - 28 = -7
        # Cover margin = -7 + 1.5 = -5.5 (lost)
        assert points[0] == 0.0

    def test_spread_push(self, simulator):
        """Spread bet pushes when cover margin is exactly 0."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.SPREAD,
            line=7.0,  # JAX +7
            team="JAX",
            draft_round=8,  # No tease
        )
        away_scores = np.array([28.0])
        home_scores = np.array([21.0])  # loses by exactly 7

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # Cover margin = -7 + 7 = 0 (push)
        assert points[0] == 0.0

    def test_vectorized_multiple_sims(self, simulator):
        """Bet points calculated correctly for multiple simulations."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=50.0,
            draft_round=8,  # No tease
        )
        # 5 simulations with different scores
        away_scores = np.array([28.0, 21.0, 35.0, 17.0, 30.0])
        home_scores = np.array([21.0, 20.0, 28.0, 14.0, 25.0])
        # Totals:          49    41    63    31    55
        # vs line 50:      L     L     W     L     W

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        assert points[0] == 0.0  # 49 < 50 -> loss
        assert points[1] == 0.0  # 41 < 50 -> loss
        assert points[2] == 20.0  # 63 - 50 = 13, capped at 10 bonus -> 20
        assert points[3] == 0.0  # 31 < 50 -> loss
        assert points[4] == 15.0  # 55 - 50 = 5 -> 10 + 5 = 15

    def test_over_bonus_capped_at_10(self, simulator):
        """Over bet bonus is capped at 10 points."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.OVER,
            line=40.0,
            draft_round=8,
        )
        away_scores = np.array([40.0])
        home_scores = np.array([35.0])  # total = 75, margin = 35

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # Bonus capped at 10, total = 20
        assert points[0] == 20.0

    def test_under_2x_bonus_capped_at_10(self, simulator):
        """Under bet gets 2x bonus but capped at 10."""
        bet = Bet(
            game_id="BUF @ JAX",
            bet_type=BetType.UNDER,
            line=50.0,
            draft_round=8,
        )
        away_scores = np.array([10.0])
        home_scores = np.array([10.0])  # total = 20, margin = 30

        points = simulator._calculate_bet_points_array(bet, away_scores, home_scores)

        # Margin = 30, bonus = min(10, 30*2) = 10
        # Total = 10 + 10 = 20
        assert points[0] == 20.0


class TestMonteCarloIntegration:
    """Test that Monte Carlo properly integrates bet scoring."""

    def test_bet_probabilities_from_simulation(self):
        """Bet probabilities should come from actual simulation results."""
        teams = [
            FantasyTeam(
                owner="TestOwner",
                qb=None, rb=None, wr=None, te=None, flex=None,
                bets=[
                    Bet(game_id="BUF @ JAX", bet_type=BetType.OVER, line=51.5, draft_round=2),
                ],
            ),
        ]
        games = {
            "BUF @ JAX": NFLGame(
                game_id="BUF @ JAX", away_team="BUF", home_team="JAX",
                spread=1.5, over_under=51.5,
            ),
        }

        sim = MonteCarloSimulator(
            teams=teams,
            games=games,
            projections={},
            n_sims=5000,
        )
        result = sim.run()

        # Check bet_probabilities structure
        assert "TestOwner" in result.bet_probabilities
        assert "bet0" in result.bet_probabilities["TestOwner"]
        bet_data = result.bet_probabilities["TestOwner"]["bet0"]
        assert "prob" in bet_data
        assert "expected_pts" in bet_data

        # Probability should be between 0 and 1
        assert 0 <= bet_data["prob"] <= 1

        # Expected points should be reasonable (0 to 20 range for winning)
        # With ~50% win rate, expected is around 7-10
        assert 0 <= bet_data["expected_pts"] <= 20

    def test_expected_points_matches_probability(self):
        """Expected points should roughly align with probability * avg payout."""
        teams = [
            FantasyTeam(
                owner="TestOwner",
                qb=None, rb=None, wr=None, te=None, flex=None,
                bets=[
                    # High probability bet (line already at current score level)
                    Bet(game_id="BUF @ JAX", bet_type=BetType.OVER, line=51.5, draft_round=1),  # Large tease
                ],
            ),
        ]
        games = {
            "BUF @ JAX": NFLGame(
                game_id="BUF @ JAX", away_team="BUF", home_team="JAX",
                spread=1.5, over_under=51.5,  # Expected total ~51.5
            ),
        }

        sim = MonteCarloSimulator(
            teams=teams,
            games=games,
            projections={},
            n_sims=10000,
        )
        result = sim.run()

        bet_data = result.bet_probabilities["TestOwner"]["bet0"]
        prob = bet_data["prob"]
        expected_pts = bet_data["expected_pts"]

        # With round 1 tease (7 points), adjusted line is 44.5
        # Expected total is 51.5, so margin ~7 points on average
        # Win probability should be high (>70%)
        # Expected points when winning = ~10 + ~7 = ~17
        # Total expected = prob * ~17

        # Sanity check: expected_pts should be reasonable given probability
        if prob > 0.5:
            # If winning more than half, expected should be meaningful
            assert expected_pts > 5


class TestEarlyGameProbabilities:
    """Test that bet probabilities stay reasonable during game progress."""

    def test_over_not_100_percent_early_game(self):
        """Over bet should NOT be 100% when score is close to expectation early in game."""
        # LAR @ CAR, O/U 46.5, score 3-0, Q1 with most of game remaining
        teams = [
            FantasyTeam(
                owner="TestOwner",
                qb=None, rb=None, wr=None, te=None, flex=None,
                bets=[
                    Bet(game_id="LAR @ CAR", bet_type=BetType.OVER, line=46.5, draft_round=3),
                ],
            ),
        ]
        games = {
            "LAR @ CAR": NFLGame(
                game_id="LAR @ CAR", away_team="LAR", home_team="CAR",
                spread=10.5, over_under=46.5,
                away_score=3, home_score=0,
                quarter=1,
                time_remaining_seconds=3300,  # ~8 min into Q1
            ),
        }

        sim = MonteCarloSimulator(
            teams=teams,
            games=games,
            projections={},
            n_sims=10000,
        )
        result = sim.run()

        prob = result.bet_probabilities["TestOwner"]["bet0"]["prob"]

        # With 3-0 early, over probability should be reasonable (30-70%), NOT 100%
        # Adjusted line = 46.5 - 5 (round 3 tease) = 41.5
        # Expected remaining ~43 points, current 3, projected ~46
        # Should be around 60-70% for over, definitely not 100%
        assert prob < 0.95, f"Over probability {prob} is too high for early game with score 3-0"
        assert prob > 0.3, f"Over probability {prob} is too low"

    def test_probability_tracks_score_vs_expectation(self):
        """Probability should reflect whether current score is ahead/behind pace."""
        # Game with O/U 46.5, halfway through
        base_game = {
            "game_id": "LAR @ CAR",
            "away_team": "LAR",
            "home_team": "CAR",
            "spread": 10.5,
            "over_under": 46.5,
            "quarter": 3,
            "time_remaining_seconds": 1800,  # Halftime (50% remaining)
        }

        # Test three scenarios at halftime:
        scenarios = [
            (14, 7, "on_pace"),    # 21 at half, expected ~23, slightly under pace
            (21, 14, "ahead"),     # 35 at half, well ahead of pace
            (7, 3, "behind"),      # 10 at half, well behind pace
        ]

        probs = {}
        for away, home, label in scenarios:
            teams = [
                FantasyTeam(
                    owner="Test",
                    qb=None, rb=None, wr=None, te=None, flex=None,
                    bets=[Bet(game_id="LAR @ CAR", bet_type=BetType.OVER, line=46.5, draft_round=8)],
                ),
            ]
            game = NFLGame(**base_game, away_score=away, home_score=home)
            sim = MonteCarloSimulator(teams=teams, games={"LAR @ CAR": game}, projections={}, n_sims=10000)
            result = sim.run()
            probs[label] = result.bet_probabilities["Test"]["bet0"]["prob"]

        # Ahead should have higher over probability than on pace, which should be higher than behind
        assert probs["ahead"] > probs["on_pace"], f"Ahead ({probs['ahead']}) should be > on_pace ({probs['on_pace']})"
        assert probs["on_pace"] > probs["behind"], f"On pace ({probs['on_pace']}) should be > behind ({probs['behind']})"

    def test_final_game_probability_is_deterministic(self):
        """For finished games, probability should be 0 or 1."""
        teams = [
            FantasyTeam(
                owner="Test",
                qb=None, rb=None, wr=None, te=None, flex=None,
                bets=[Bet(game_id="LAR @ CAR", bet_type=BetType.OVER, line=46.5, draft_round=8)],
            ),
        ]
        # Final score 28-21 = 49, over 46.5 wins
        game = NFLGame(
            game_id="LAR @ CAR", away_team="LAR", home_team="CAR",
            spread=10.5, over_under=46.5,
            away_score=28, home_score=21,
            quarter=5,  # Final
            time_remaining_seconds=0,
        )
        sim = MonteCarloSimulator(teams=teams, games={"LAR @ CAR": game}, projections={}, n_sims=1000)
        result = sim.run()

        prob = result.bet_probabilities["Test"]["bet0"]["prob"]
        assert prob == 1.0, f"Final game over should be 100% when total (49) > line (46.5)"


class TestCreateDefaultGames:
    """Test default game creation."""

    def test_creates_six_games(self):
        """Should create 6 wildcard games."""
        games = create_default_games()
        assert len(games) == 6

    def test_all_games_have_lines(self):
        """All games should have spread and O/U."""
        games = create_default_games()
        for game_id, game in games.items():
            assert game.spread != 0 or game.over_under != 0
            assert game.over_under > 30  # Reasonable O/U

    def test_game_ids_match_format(self):
        """Game IDs should be in 'AWAY @ HOME' format."""
        games = create_default_games()
        for game_id in games.keys():
            assert '@' in game_id
            parts = game_id.split('@')
            assert len(parts) == 2
