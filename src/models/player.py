from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Position(Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"


@dataclass
class PlayerProjection:
    """Full-game projection for a player."""
    name: str
    team: str
    position: Position

    # Passing (QB only)
    pass_att: float = 0.0
    pass_cmp: float = 0.0
    pass_yds: float = 0.0
    pass_tds: float = 0.0
    ints: float = 0.0

    # Rushing
    rush_att: float = 0.0
    rush_yds: float = 0.0
    rush_tds: float = 0.0

    # Receiving
    rec: float = 0.0
    rec_yds: float = 0.0
    rec_tds: float = 0.0

    # Turnovers
    fumbles_lost: float = 0.0

    @property
    def yards_per_reception(self) -> float:
        """Average yards per reception."""
        return self.rec_yds / self.rec if self.rec > 0 else 0.0

    @property
    def yards_per_rush(self) -> float:
        """Average yards per rush attempt."""
        return self.rush_yds / self.rush_att if self.rush_att > 0 else 0.0

    @property
    def yards_per_pass_completion(self) -> float:
        """Average yards per pass completion."""
        return self.pass_yds / self.pass_cmp if self.pass_cmp > 0 else 0.0

    def scale(self, fraction: float) -> 'PlayerProjection':
        """Return a new projection scaled by the given fraction (for time remaining)."""
        return PlayerProjection(
            name=self.name,
            team=self.team,
            position=self.position,
            pass_att=self.pass_att * fraction,
            pass_cmp=self.pass_cmp * fraction,
            pass_yds=self.pass_yds * fraction,
            pass_tds=self.pass_tds * fraction,
            ints=self.ints * fraction,
            rush_att=self.rush_att * fraction,
            rush_yds=self.rush_yds * fraction,
            rush_tds=self.rush_tds * fraction,
            rec=self.rec * fraction,
            rec_yds=self.rec_yds * fraction,
            rec_tds=self.rec_tds * fraction,
            fumbles_lost=self.fumbles_lost * fraction,
        )


@dataclass
class PlayerStats:
    """Actual or simulated stats for a player."""
    pass_yds: float = 0.0
    pass_tds: int = 0
    ints: int = 0
    rush_yds: float = 0.0
    rush_tds: int = 0
    rec: int = 0
    rec_yds: float = 0.0
    rec_tds: int = 0
    fumbles_lost: int = 0

    def __add__(self, other: 'PlayerStats') -> 'PlayerStats':
        """Add two stats together (current + simulated remaining)."""
        return PlayerStats(
            pass_yds=self.pass_yds + other.pass_yds,
            pass_tds=self.pass_tds + other.pass_tds,
            ints=self.ints + other.ints,
            rush_yds=self.rush_yds + other.rush_yds,
            rush_tds=self.rush_tds + other.rush_tds,
            rec=self.rec + other.rec,
            rec_yds=self.rec_yds + other.rec_yds,
            rec_tds=self.rec_tds + other.rec_tds,
            fumbles_lost=self.fumbles_lost + other.fumbles_lost,
        )
