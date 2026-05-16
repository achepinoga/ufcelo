import pandas as pd


def peak_elo_leaderboard(fighters: dict, logs: list = None) -> pd.DataFrame:
    # Build weight_class and last_fight_date lookups from logs
    wc_map:   dict[str, str] = {}
    last_map: dict[str, str] = {}
    if logs:
        for log in logs:
            if log.get("voided"):
                continue
            for fid in [log["fighter_a"], log["fighter_b"]]:
                d = log["date"]
                if d > last_map.get(fid, ""):
                    last_map[fid] = d
                    if log.get("weight_class"):
                        wc_map[fid] = log["weight_class"]

    rows = []
    for fid, f in fighters.items():
        if f.fight_count == 0:
            continue
        peak = max(elo for _, elo in f.elo_history) if f.elo_history else f.elo
        rows.append({
            "fighter_id":     fid,
            "fighter":        f.name,
            "weight_class":   wc_map.get(fid, ""),
            "peak_elo":       round(peak, 1),
            "current_elo":    round(f.elo, 1),
            "fights":         f.fight_count,
            "win_streak":     f.win_streak,
            "last_fight_date": last_map.get(fid, ""),
        })
    df = pd.DataFrame(rows).sort_values("peak_elo", ascending=False).reset_index(drop=True)
    df.index += 1
    return df


def upset_index(logs: list, top_n: int = 100) -> pd.DataFrame:
    rows = []
    for log in logs:
        if log["voided"] or log["actual_a"] is None:
            continue
        exp_a = log["exp_a"]
        actual_a = log["actual_a"]

        # Only count decisive results as upsets (not draws)
        if actual_a not in (0.0, 1.0):
            continue

        expected_winner = log["fighter_a"] if exp_a >= 0.5 else log["fighter_b"]
        actual_winner = log["winner"]

        if actual_winner != expected_winner:
            upset_prob = round(min(exp_a, 1 - exp_a), 4)
            rows.append({
                "date":          log["date"],
                "event":         log["event"],
                "winner":        actual_winner,
                "loser":         log["fighter_b"] if actual_winner == log["fighter_a"] else log["fighter_a"],
                "result":        log["result"],
                "upset_prob":    upset_prob,        # probability assigned to the winner
                "elo_winner_before": log["elo_b_before"] if actual_winner == log["fighter_b"] else log["elo_a_before"],
                "elo_loser_before":  log["elo_a_before"] if actual_winner == log["fighter_b"] else log["elo_b_before"],
            })

    df = (pd.DataFrame(rows)
          .sort_values("upset_prob")
          .head(top_n)
          .reset_index(drop=True))
    df.index += 1
    return df


def strength_of_schedule(logs: list) -> pd.DataFrame:
    """Mean opponent Elo at time of fight — the key anti-farming metric."""
    opp_elos: dict[str, list] = {}
    for log in logs:
        if log["voided"]:
            continue
        a, b = log["fighter_a"], log["fighter_b"]
        opp_elos.setdefault(a, []).append(log["elo_b_before"])
        opp_elos.setdefault(b, []).append(log["elo_a_before"])

    rows = [
        {"fighter_id": fid, "mean_opp_elo": round(sum(elos) / len(elos), 1), "fights": len(elos)}
        for fid, elos in opp_elos.items()
    ]
    return (pd.DataFrame(rows)
            .sort_values("mean_opp_elo", ascending=False)
            .reset_index(drop=True))


def elo_timeline(fighters: dict, fighter_ids: list) -> pd.DataFrame:
    """Returns Elo over time for a list of specific fighters."""
    rows = []
    for fid in fighter_ids:
        f = fighters.get(fid)
        if not f:
            continue
        for date_iso, elo in f.elo_history:
            rows.append({"fighter_id": fid, "fighter": f.name, "date": date_iso, "elo": elo})
    return pd.DataFrame(rows).sort_values(["fighter_id", "date"])


def fights_log_df(fighters: dict, logs: list) -> pd.DataFrame:
    name_map = {fid: f.name for fid, f in fighters.items()}
    rows = []
    for log in logs:
        if log.get("voided"):
            continue
        a_id = log["fighter_a"]
        b_id = log["fighter_b"]
        rows.append({
            "date":          log["date"],
            "event":         log["event"],
            "weight_class":  log.get("weight_class", ""),
            "fighter_a_id":  a_id,
            "fighter_a":     name_map.get(a_id, a_id.replace("_", " ").title()),
            "fighter_b_id":  b_id,
            "fighter_b":     name_map.get(b_id, b_id.replace("_", " ").title()),
            "winner_id":     log.get("winner") or "",
            "result":        log["result"],
            "elo_a_before":  log["elo_a_before"],
            "elo_a_after":   round(log["elo_a_before"] + log["delta_a"], 1),
            "delta_a":       round(log["delta_a"], 1),
            "elo_b_before":  log["elo_b_before"],
            "elo_b_after":   round(log["elo_b_before"] + log["delta_b"], 1),
            "delta_b":       round(log["delta_b"], 1),
            "exp_a":         log["exp_a"],
        })
    return pd.DataFrame(rows)


def save_events_json(fighters: dict, logs: list, upcoming_raw: list) -> None:
    """Generates events.json: recent past events + upcoming with announced cards."""
    import json
    from datetime import date as date_cls

    name_map = {fid: f.name for fid, f in fighters.items()}

    # Build recent events index from logs (first log per event = main event fight)
    seen: dict[str, dict] = {}
    for log in logs:
        if log.get("voided"):
            continue
        ev = log["event"]
        if ev not in seen:
            fa = name_map.get(log["fighter_a"], log["fighter_a"].replace("_", " ").title())
            fb = name_map.get(log["fighter_b"], log["fighter_b"].replace("_", " ").title())
            seen[ev] = {
                "name":       ev,
                "date":       str(log["date"]),
                "fight_count": 0,
                "main_event": f"{fa} vs {fb}",
            }
        seen[ev]["fight_count"] += 1

    recent = sorted(seen.values(), key=lambda e: e["date"], reverse=True)[:15]

    # Format upcoming events
    upcoming = []
    for ev in upcoming_raw:
        upcoming.append({
            "name":     ev["name"],
            "date":     str(ev["date"]),
            "location": ev.get("location", ""),
            "card":     ev.get("card", [])[:6],
        })

    payload = {
        "updated":  str(date_cls.today()),
        "recent":   recent,
        "upcoming": upcoming,
    }

    with open("events.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"events.json: {len(recent)} recent, {len(upcoming)} upcoming events")


def save_all_outputs(fighters: dict, logs: list, append_fights: bool = False):
    import os
    peak_elo_leaderboard(fighters, logs).to_csv("leaderboard.csv", index=True)
    upset_index(logs).to_csv("upset_index.csv", index=True)
    strength_of_schedule(logs).to_csv("strength_of_schedule.csv", index=False)

    new_fights = fights_log_df(fighters, logs)
    if append_fights and os.path.exists("fights_log.csv"):
        existing = pd.read_csv("fights_log.csv", dtype=str)
        pd.concat([existing, new_fights.astype(str)], ignore_index=True).to_csv("fights_log.csv", index=False)
    else:
        new_fights.to_csv("fights_log.csv", index=False)

    print("Outputs written: leaderboard.csv, upset_index.csv, strength_of_schedule.csv, fights_log.csv")
