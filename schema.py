from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, List, Tuple


class ResultType(Enum):
    KO = "KO"
    TKO = "TKO"
    SUBMISSION = "SUB"
    UNANIMOUS_DECISION = "UD"
    MAJORITY_DECISION = "MD"
    SPLIT_DECISION = "SD"
    TECHNICAL_DECISION = "TD"
    DRAW = "DRAW"
    NO_CONTEST = "NC"
    DISQUALIFICATION = "DQ"


RESULT_MULTIPLIER = {
    ResultType.NO_CONTEST:         0.00,
    ResultType.DISQUALIFICATION:   0.50,
    ResultType.SPLIT_DECISION:     0.75,
    ResultType.MAJORITY_DECISION:  0.85,
    ResultType.TECHNICAL_DECISION: 0.90,
    ResultType.DRAW:               1.00,
    ResultType.UNANIMOUS_DECISION: 1.00,
    ResultType.SUBMISSION:         1.15,
    ResultType.TKO:                1.25,
    ResultType.KO:                 1.35,
}


@dataclass
class Fighter:
    id: str
    name: str
    elo: float = 800.0
    fight_count: int = 0
    win_streak: int = 0
    elo_history: List[Tuple[str, float]] = field(default_factory=list)  # (date_iso, elo)


@dataclass
class Fight:
    date: date
    event: str
    fighter_a_id: str
    fighter_b_id: str
    winner_id: Optional[str]   # None = draw or NC
    result_type: ResultType
    weight_class: str
    event_sequence: int = 0    # fight order within event (prelims before main card)
