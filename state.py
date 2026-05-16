import json
from datetime import date
from schema import Fighter

STATE_PATH = "state.json"


def save_state(fighters: dict, last_processed_date: date, path: str = STATE_PATH):
    data = {
        "last_processed_date": last_processed_date.isoformat(),
        "fighters": {
            fid: {
                "name": f.name,
                "elo": round(f.elo, 4),
                "fight_count": f.fight_count,
                "win_streak": f.win_streak,
                "elo_history": f.elo_history,
            }
            for fid, f in fighters.items()
        },
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
    print(f"State saved: {len(fighters)} fighters, through {last_processed_date}")


def load_state(path: str = STATE_PATH) -> tuple:
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)

    fighters = {}
    for fid, d in data["fighters"].items():
        f = Fighter(id=fid, name=d["name"])
        f.elo = d["elo"]
        f.fight_count = d["fight_count"]
        f.win_streak = d["win_streak"]
        f.elo_history = d["elo_history"]
        fighters[fid] = f

    last_date = date.fromisoformat(data["last_processed_date"])
    print(f"State loaded: {len(fighters)} fighters, last processed {last_date}")
    return fighters, last_date
