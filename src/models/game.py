from dataclasses import dataclass
from typing import Optional


@dataclass
class NFLGame:
    """Represents an NFL game with its current state."""
    game_id: str  # e.g., "SF @ PHI"
    away_team: str
    home_team: str
    spread: float  # Negative = home favored, Positive = away favored
    over_under: float

    # Live state
    away_score: int = 0
    home_score: int = 0
    time_remaining_seconds: int = 3600  # 60 minutes total
    quarter: int = 0  # 0 = not started, 1-4 = in progress, 5 = final

    @property
    def is_final(self) -> bool:
        """Check if game is complete."""
        return self.quarter == 5 or (self.quarter == 4 and self.time_remaining_seconds == 0)

    @property
    def fraction_remaining(self) -> float:
        """Fraction of game remaining (0.0 to 1.0)."""
        if self.is_final:
            return 0.0
        return self.time_remaining_seconds / 3600

    @property
    def total_score(self) -> int:
        """Current total score."""
        return self.away_score + self.home_score

    def derive_expected_scores(self) -> tuple[float, float]:
        """
        Derive expected final scores from spread and O/U.

        Solving system:
        - O/U = away_exp + home_exp
        - spread = home_exp - away_exp (negative = home favored)

        Returns (away_expected, home_expected)
        """
        home_exp = (self.over_under - self.spread) / 2
        away_exp = (self.over_under + self.spread) / 2
        return away_exp, home_exp


@dataclass
class GameResult:
    """Final or simulated game result."""
    away_score: int
    home_score: int

    @property
    def total(self) -> int:
        return self.away_score + self.home_score

    @property
    def margin(self) -> int:
        """Home team margin (positive = home won)."""
        return self.home_score - self.away_score
