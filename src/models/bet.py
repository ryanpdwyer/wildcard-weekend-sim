from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BetType(Enum):
    SPREAD = "spread"
    OVER = "over"
    UNDER = "under"


# Tease bonus lookup tables by draft round
OU_TEASE_BY_ROUND = {1: 7.0, 2: 6.0, 3: 5.0, 4: 4.0, 5: 3.0, 6: 2.0, 7: 1.0, 8: 0.0}
SPREAD_TEASE_BY_ROUND = {1: 3.5, 2: 3.0, 3: 2.5, 4: 2.0, 5: 1.5, 6: 1.0, 7: 0.5, 8: 0.0}


@dataclass
class Bet:
    """Represents a spread or over/under bet."""
    game_id: str  # e.g., "SF @ PHI"
    bet_type: BetType
    line: float  # The spread or O/U number
    team: Optional[str] = None  # For spreads, which team is being bet on
    draft_round: int = 8  # 1-8 for tease calculation

    @property
    def tease_bonus(self) -> float:
        """Calculate tease adjustment based on draft round."""
        if self.bet_type == BetType.SPREAD:
            return SPREAD_TEASE_BY_ROUND.get(self.draft_round, 0.0)
        else:
            return OU_TEASE_BY_ROUND.get(self.draft_round, 0.0)

    @property
    def adjusted_line(self) -> float:
        """
        Line after tease adjustment (more favorable for bettor).

        For spreads: +X means team getting points, so adding tease helps
        For over: lower threshold is better, so subtract tease
        For under: higher threshold is better, so add tease
        """
        if self.bet_type == BetType.SPREAD:
            # If line is +1.5 and tease is 2.5, adjusted is +4.0 (more points in our favor)
            return self.line + self.tease_bonus
        elif self.bet_type == BetType.OVER:
            # If O/U is 46.5 and tease is 5, adjusted is 41.5 (lower bar to clear)
            return self.line - self.tease_bonus
        else:  # UNDER
            # If O/U is 46.5 and tease is 5, adjusted is 51.5 (higher ceiling)
            return self.line + self.tease_bonus

    def __repr__(self) -> str:
        if self.bet_type == BetType.SPREAD:
            sign = "+" if self.line >= 0 else ""
            return f"Bet({self.game_id}: {self.team} {sign}{self.line}, R{self.draft_round})"
        elif self.bet_type == BetType.OVER:
            return f"Bet({self.game_id}: o{self.line}, R{self.draft_round})"
        else:
            return f"Bet({self.game_id}: u{self.line}, R{self.draft_round})"
