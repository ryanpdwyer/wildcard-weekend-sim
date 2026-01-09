from dataclasses import dataclass, field
from typing import List, Optional

from .player import PlayerProjection, Position
from .bet import Bet


@dataclass
class FantasyTeam:
    """A fantasy team with its roster and bets."""
    owner: str
    qb: Optional[str] = None  # Player name
    rb: Optional[str] = None
    wr: Optional[str] = None
    te: Optional[str] = None
    flex: Optional[str] = None  # RB, WR, or TE
    bets: List[Bet] = field(default_factory=list)  # 3 bets

    @property
    def all_player_names(self) -> List[str]:
        """Get all player names on this roster."""
        players = [self.qb, self.rb, self.wr, self.te, self.flex]
        return [p for p in players if p is not None]

    def __repr__(self) -> str:
        return (
            f"FantasyTeam({self.owner}: "
            f"QB={self.qb}, RB={self.rb}, WR={self.wr}, TE={self.te}, "
            f"FLEX={self.flex}, bets={len(self.bets)})"
        )
