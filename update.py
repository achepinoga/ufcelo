"""
Entry point for both initial bootstrap and incremental updates.

First run (no state.json):  scrapes all UFC history from ufcstats.com
Subsequent runs:            scrapes only events after last processed date
"""

import os
from datetime import date
from itertools import groupby

from schema import Fighter
from state import save_state, load_state, STATE_PATH
from scraper import get_all_events, scrape_events
from elo_engine import process_event
from outputs import save_all_outputs


def ensure_fighters(fight, fighters: dict):
    for fid in [fight.fighter_a_id, fight.fighter_b_id]:
        if fid not in fighters:
            fighters[fid] = Fighter(id=fid, name=fid.replace("_", " ").title())


def run(fighters: dict, fights: list) -> list:
    """Process a list of fights chronologically. Returns all fight logs."""
    all_logs = []

    sorted_fights = sorted(fights, key=lambda f: (f.date, f.event, f.event_sequence))
    event_groups = groupby(sorted_fights, key=lambda f: (f.date, f.event))

    for (event_date, event_name), event_fights in event_groups:
        event_list = list(event_fights)
        for fight in event_list:
            ensure_fighters(fight, fighters)
        logs = process_event(event_list, fighters)
        all_logs.extend(logs)

    return all_logs


def main():
    all_logs = []

    if os.path.exists(STATE_PATH):
        fighters, last_date = load_state()
        after_date = last_date
    else:
        print("No state file found — running full historical bootstrap")
        fighters = {}
        after_date = date(1993, 1, 1)  # before UFC 1 (Nov 12, 1993)

    events = get_all_events(after_date=after_date)
    if not events:
        print("No new events found. System is up to date.")
        return

    # Checkpoint: save state every 50 events so progress is not lost on failure
    def checkpoint(fights_so_far, last_event):
        if fights_so_far:
            temp_fighters = dict(fighters)  # shallow copy for checkpoint
            logs = run(temp_fighters, fights_so_far)
            save_state(temp_fighters, last_event["date"], "state_checkpoint.json")
            print(f"  [checkpoint] saved after {last_event['name']}")

    fights = scrape_events(events)

    if not fights:
        print("No fights scraped. Check scraper selectors against ufcstats.com HTML.")
        return

    print(f"\nProcessing {len(fights)} fights through Elo engine...")
    all_logs = run(fighters, fights)

    last_date = max(f.date for f in fights)
    save_state(fighters, last_date)
    save_all_outputs(fighters, all_logs)

    # Clean up checkpoint file if it exists
    if os.path.exists("state_checkpoint.json"):
        os.remove("state_checkpoint.json")

    print(f"\nDone. Processed {len(fights)} fights across {len(set(f.event for f in fights))} events.")
    print(f"Total fighters rated: {len(fighters)}")


if __name__ == "__main__":
    main()
