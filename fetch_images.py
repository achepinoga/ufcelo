"""
Download fighter images from UFC.com official athlete pages.
Saves to fighters/{fighter_id}.jpg — skips files that already exist.

Usage:
    pip install requests
    python fetch_images.py
"""

import csv
import re
import time
import requests
from pathlib import Path
from datetime import date, timedelta

FIGHTERS_DIR = Path("fighters")
FIGHTERS_DIR.mkdir(exist_ok=True)

TOP_N       = 15
SLEEP_SEC   = 0.4         # polite delay between requests
DIVISIONS = [
    "Heavyweight", "Light Heavyweight", "Middleweight",
    "Welterweight", "Lightweight", "Featherweight", "Bantamweight",
    "Flyweight", "Women's Strawweight", "Women's Flyweight", "Women's Bantamweight",
]

# 18 calendar months back (not 18*30 days — avoids off-by-a-few-days edge cases)
today = date.today()
cutoff_month = today.month - 18
cutoff_year  = today.year + cutoff_month // 12 if cutoff_month <= 0 else today.year
cutoff_month = cutoff_month % 12 or 12
cutoff = date(cutoff_year, cutoff_month, today.day).isoformat()

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def load_leaderboard(path="leaderboard.csv"):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def get_targets(rows):
    active = [r for r in rows if r.get("last_fight_date", "") >= cutoff]
    needed: dict[str, str] = {}

    p4p = sorted(active, key=lambda r: float(r.get("current_elo") or 0), reverse=True)
    for r in p4p[:TOP_N]:
        needed[r["fighter_id"]] = r["fighter"]

    for div in DIVISIONS:
        div_rows = [r for r in active if r.get("weight_class") == div]
        div_rows.sort(key=lambda r: float(r.get("current_elo") or 0), reverse=True)
        for r in div_rows[:TOP_N]:
            needed[r["fighter_id"]] = r["fighter"]

    return needed


def name_to_slug(name: str) -> list[str]:
    """Generate UFC.com slug candidates from a fighter name."""
    clean = name.lower()
    clean = re.sub(r"['’\.]", "", clean)  # remove apostrophes, dots
    clean = re.sub(r"[^a-z0-9\s-]", "", clean)
    parts = clean.split()
    slugs = []
    # Standard: all parts joined with hyphens
    slugs.append("-".join(parts))
    # Without middle name (first + last only)
    if len(parts) > 2:
        slugs.append(f"{parts[0]}-{parts[-1]}")
    return slugs


def ufc_image_url(name: str) -> str | None:
    for slug in name_to_slug(name):
        try:
            r = SESSION.get(
                f"https://www.ufc.com/athlete/{slug}",
                timeout=12,
                allow_redirects=True,
            )
            if r.status_code != 200:
                continue
            m = re.search(r'property="og:image" content="([^"]+)"', r.text)
            if m:
                url = m.group(1)
                # Skip generic UFC logo / event images (not fighter-specific)
                if "ufc-logo" in url or "default" in url.lower():
                    continue
                return url
        except Exception:
            pass
        time.sleep(0.2)
    return None


def download(url: str, dest: Path) -> bool:
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 200 and len(r.content) > 2000:
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def main():
    rows   = load_leaderboard()
    needed = get_targets(rows)
    print(f"Targeting {len(needed)} unique fighters\n")

    ok = fail = skipped = 0
    for fid, name in sorted(needed.items(), key=lambda x: x[1]):
        dest = FIGHTERS_DIR / f"{fid}.jpg"
        if dest.exists():
            skipped += 1
            print(f"  skip  {name}")
            continue

        img_url = ufc_image_url(name)
        time.sleep(SLEEP_SEC)

        if img_url and download(img_url, dest):
            print(f"  OK    {name}  ({img_url.split('/')[-1]})")
            ok += 1
        else:
            print(f"  MISS  {name}")
            fail += 1

    print(f"\n  saved {ok}  not found {fail}  skipped {skipped}")


if __name__ == "__main__":
    main()
