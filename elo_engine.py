import math
from schema import Fighter, Fight, ResultType, RESULT_MULTIPLIER

D             = 600.0   # scaling constant — flatter curve than chess (400)
K_BASE        = 40.0    # base K value
K_HALFLIFE    = 10      # K halves after this many fights
K_FLOOR_RATIO = 0.55    # K floors at 55% of base
STREAK_ALPHA  = 0.05    # streak modifier strength
STREAK_CAP    = 1.15    # maximum streak modifier


def adaptive_k(fight_count: int) -> float:
    k = K_BASE / (1 + fight_count / K_HALFLIFE)
    return max(k, K_BASE * K_FLOOR_RATIO)


def streak_modifier(streak_a: int, streak_b: int) -> float:
    n = max(streak_a, streak_b)
    if n == 0:
        return 1.0
    return min(STREAK_CAP, 1 + STREAK_ALPHA * math.log(n + 1))


def expected_score(elo_a: float, elo_b: float) -> float:
    return 1 / (1 + 10 ** ((elo_b - elo_a) / D))


def process_event(fights: list, fighters: dict) -> list:
    """
    Process all fights in one event.
    Expected values are computed from a pre-event Elo snapshot so that
    fights on the same card don't influence each other's expectations.
    """
    snapshot = {fid: f.elo for fid, f in fighters.items()}
    pending = []
    logs = []

    for fight in fights:
        a = fighters[fight.fighter_a_id]
        b = fighters[fight.fighter_b_id]

        elo_a = snapshot.get(fight.fighter_a_id, 800.0)
        elo_b = snapshot.get(fight.fighter_b_id, 800.0)

        exp_a = expected_score(elo_a, elo_b)

        if fight.result_type == ResultType.NO_CONTEST:
            logs.append({
                "date": fight.date.isoformat(), "event": fight.event,
                "fighter_a": fight.fighter_a_id, "fighter_b": fight.fighter_b_id,
                "winner": None, "result": fight.result_type.value,
                "weight_class": fight.weight_class,
                "exp_a": round(exp_a, 4), "actual_a": None,
                "delta_a": 0.0, "delta_b": 0.0,
                "elo_a_before": round(elo_a, 1), "elo_b_before": round(elo_b, 1),
                "voided": True,
            })
            continue

        if fight.winner_id == fight.fighter_a_id:
            actual_a, actual_b = 1.0, 0.0
        elif fight.winner_id == fight.fighter_b_id:
            actual_a, actual_b = 0.0, 1.0
        else:
            actual_a, actual_b = 0.5, 0.5

        M = RESULT_MULTIPLIER[fight.result_type]
        S = streak_modifier(a.win_streak, b.win_streak)
        K_eff = ((adaptive_k(a.fight_count) + adaptive_k(b.fight_count)) / 2) * S

        delta_a = K_eff * M * (actual_a - exp_a)
        delta_b = K_eff * M * (actual_b - (1 - exp_a))

        pending.append((fight, delta_a, delta_b, actual_a, actual_b))
        logs.append({
            "date": fight.date.isoformat(), "event": fight.event,
            "fighter_a": fight.fighter_a_id, "fighter_b": fight.fighter_b_id,
            "winner": fight.winner_id, "result": fight.result_type.value,
            "weight_class": fight.weight_class,
            "exp_a": round(exp_a, 4), "actual_a": actual_a,
            "delta_a": round(delta_a, 2), "delta_b": round(delta_b, 2),
            "elo_a_before": round(elo_a, 1), "elo_b_before": round(elo_b, 1),
            "K_eff": round(K_eff, 2), "M": M, "S": round(S, 3),
            "voided": False,
        })

    # Apply all deltas after computing all expectations
    for fight, delta_a, delta_b, actual_a, actual_b in pending:
        a = fighters[fight.fighter_a_id]
        b = fighters[fight.fighter_b_id]

        a.elo += delta_a
        b.elo += delta_b
        a.elo_history.append((fight.date.isoformat(), round(a.elo, 2)))
        b.elo_history.append((fight.date.isoformat(), round(b.elo, 2)))
        a.fight_count += 1
        b.fight_count += 1

        if actual_a == 1.0:
            a.win_streak += 1
            b.win_streak = 0
        elif actual_b == 1.0:
            b.win_streak += 1
            a.win_streak = 0
        else:
            a.win_streak = 0
            b.win_streak = 0

    return logs
