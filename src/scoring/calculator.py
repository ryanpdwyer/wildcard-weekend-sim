"""Fantasy point calculation based on league scoring rules."""

from ..models.player import PlayerStats, PlayerProjection, Position
from ..models.game import GameResult
from ..models.bet import Bet, BetType

# QB Scoring constants
QB_PASS_YARDS_PER_POINT = 25
QB_PASS_TD_POINTS = 4
QB_RUSH_TD_POINTS = 6
QB_RUSH_YARDS_PER_POINT = 20
TURNOVER_POINTS = -2

# Skill position scoring constants
SKILL_YARDS_PER_POINT = 10
SKILL_TD_POINTS = 6
PPR_POINTS = 0.5

# Bet scoring constants
SPREAD_BASE_POINTS = 10
SPREAD_BONUS_PER_POINT = 1
SPREAD_MAX_BONUS = 10

OU_BASE_POINTS = 10
OU_OVER_BONUS_PER_POINT = 1
OU_UNDER_BONUS_PER_POINT = 2
OU_MAX_BONUS = 10


def calculate_qb_points(stats: PlayerStats) -> float:
    """
    Calculate fantasy points for a QB.

    Scoring:
    - 1 pt per 25 passing yards
    - 4 pts per passing TD
    - 6 pts per rushing TD
    - 1 pt per 20 rushing yards
    - -2 pts per turnover (INT or fumble lost)
    """
    return (
        stats.pass_yds / QB_PASS_YARDS_PER_POINT +
        stats.pass_tds * QB_PASS_TD_POINTS +
        stats.rush_yds / QB_RUSH_YARDS_PER_POINT +
        stats.rush_tds * QB_RUSH_TD_POINTS +
        (stats.ints + stats.fumbles_lost) * TURNOVER_POINTS
    )


def calculate_skill_points(stats: PlayerStats) -> float:
    """
    Calculate fantasy points for RB/WR/TE.

    Scoring:
    - 0.5 PPR (points per reception)
    - 1 pt per 10 yards (rushing + receiving)
    - 6 pts per TD (rushing + receiving)
    - -2 pts per fumble lost
    """
    total_yards = stats.rush_yds + stats.rec_yds
    total_tds = stats.rush_tds + stats.rec_tds
    return (
        total_yards / SKILL_YARDS_PER_POINT +
        total_tds * SKILL_TD_POINTS +
        stats.rec * PPR_POINTS +
        stats.fumbles_lost * TURNOVER_POINTS
    )


def calculate_player_points(stats: PlayerStats, position: Position) -> float:
    """Calculate fantasy points for any position."""
    if position == Position.QB:
        return calculate_qb_points(stats)
    else:
        return calculate_skill_points(stats)


def calculate_fantasy_points(proj: PlayerProjection) -> float:
    """Calculate projected fantasy points from a PlayerProjection."""
    if proj.position == Position.QB:
        return (
            proj.pass_yds / QB_PASS_YARDS_PER_POINT +
            proj.pass_tds * QB_PASS_TD_POINTS +
            proj.rush_yds / QB_RUSH_YARDS_PER_POINT +
            proj.rush_tds * QB_RUSH_TD_POINTS +
            (proj.ints + proj.fumbles_lost) * TURNOVER_POINTS
        )
    else:
        total_yards = proj.rush_yds + proj.rec_yds
        total_tds = proj.rush_tds + proj.rec_tds
        return (
            total_yards / SKILL_YARDS_PER_POINT +
            total_tds * SKILL_TD_POINTS +
            proj.rec * PPR_POINTS +
            proj.fumbles_lost * TURNOVER_POINTS
        )


def calculate_spread_points(bet: Bet, result: GameResult) -> float:
    """
    Calculate spread bet points.

    Scoring:
    - 10 pts if bet is won
    - +1 pt bonus for each additional covering point (max 10 bonus)

    Example: GB -4 (adjusted), actual GB 32 JAX 20.
    GB wins by 12, covers by 8 (12 - 4 = 8).
    Points = 10 + min(10, 8) = 18

    The bet.adjusted_line already includes the tease bonus.
    """
    if bet.bet_type != BetType.SPREAD:
        raise ValueError(f"Expected SPREAD bet, got {bet.bet_type}")

    # Determine actual margin from the bet team's perspective
    # bet.line is the spread for the team being bet on
    # Positive line means they're the underdog (getting points)
    # Negative line means they're the favorite (giving points)

    # First, figure out which side of the game we bet on
    away_team, home_team = _parse_game_teams(bet.game_id)

    if bet.team == away_team:
        actual_margin = result.away_score - result.home_score
    else:  # bet on home team
        actual_margin = result.home_score - result.away_score

    # Cover margin = actual margin + adjusted line
    # If we bet underdog +4.5 and they lose by 3, cover margin = -3 + 4.5 = +1.5 (win)
    # If we bet favorite -4.5 and they win by 7, cover margin = 7 + (-4.5) = +2.5 (win)
    cover_margin = actual_margin + bet.adjusted_line

    if cover_margin > 0:
        # Won the bet
        bonus = min(SPREAD_MAX_BONUS, cover_margin)
        return SPREAD_BASE_POINTS + bonus
    elif cover_margin == 0:
        # Push - no points
        return 0.0
    else:
        # Lost the bet
        return 0.0


def calculate_ou_points(bet: Bet, result: GameResult) -> float:
    """
    Calculate over/under bet points.

    Scoring:
    - 10 pts if bet is won
    - Over: +1 pt bonus per covering point (max 10)
    - Under: +2 pts bonus per covering point (max 10)

    The bet.adjusted_line already includes the tease bonus.
    """
    if bet.bet_type not in (BetType.OVER, BetType.UNDER):
        raise ValueError(f"Expected OVER/UNDER bet, got {bet.bet_type}")

    total = result.total

    if bet.bet_type == BetType.OVER:
        margin = total - bet.adjusted_line
        if margin > 0:
            bonus = min(OU_MAX_BONUS, margin * OU_OVER_BONUS_PER_POINT)
            return OU_BASE_POINTS + bonus
        elif margin == 0:
            return 0.0  # Push
        else:
            return 0.0  # Lost
    else:  # UNDER
        margin = bet.adjusted_line - total
        if margin > 0:
            bonus = min(OU_MAX_BONUS, margin * OU_UNDER_BONUS_PER_POINT)
            return OU_BASE_POINTS + bonus
        elif margin == 0:
            return 0.0  # Push
        else:
            return 0.0  # Lost


def calculate_bet_points(bet: Bet, result: GameResult) -> float:
    """Calculate points for any bet type."""
    if bet.bet_type == BetType.SPREAD:
        return calculate_spread_points(bet, result)
    else:
        return calculate_ou_points(bet, result)


def _parse_game_teams(game_id: str) -> tuple[str, str]:
    """Parse game ID like 'SF @ PHI' into (away, home) teams."""
    parts = game_id.split('@')
    if len(parts) != 2:
        raise ValueError(f"Invalid game ID format: {game_id}")
    away = parts[0].strip()
    home = parts[1].strip()
    return away, home
