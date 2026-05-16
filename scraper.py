import time
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup
from schema import Fight, ResultType
from normalize import normalize_result, resolve_id

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UFC-Elo-Research/1.0)"
}
REQUEST_DELAY = 1.5   # seconds between requests — be polite
MAX_RETRIES   = 3


def _get(url: str) -> BeautifulSoup:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Retry {attempt + 1} for {url}: {e}")
                time.sleep(3)
            else:
                raise
    raise RuntimeError(f"Failed to fetch {url}")


def get_all_events(after_date: date = None) -> list:
    """
    Returns list of {name, url, date} dicts for all completed UFC events,
    sorted chronologically. If after_date is given, only returns events after it.
    """
    url = "http://ufcstats.com/statistics/events/completed?page=all"
    print(f"Fetching event list from ufcstats.com...")
    soup = _get(url)

    events = []
    for row in soup.select("tr.b-statistics__table-row"):
        link = row.select_one("a.b-link")
        if not link:
            continue

        # Date is inside the same cell as the link
        date_span = row.select_one("span.b-statistics__date")
        if not date_span:
            continue

        try:
            event_date = datetime.strptime(date_span.text.strip(), "%B %d, %Y").date()
        except ValueError:
            continue

        if after_date and event_date <= after_date:
            continue

        events.append({
            "name": link.text.strip(),
            "url": link["href"],
            "date": event_date,
        })

    events.sort(key=lambda e: e["date"])
    print(f"Found {len(events)} events to process")
    return events


def scrape_event(event: dict) -> list:
    """
    Returns list of Fight objects for a single event page.
    """
    soup = _get(event["url"])
    fights = []

    rows = soup.select("tr.b-fight-details__table-row[data-link]")

    for sequence, row in enumerate(rows):
        cols = row.select("td.b-fight-details__table-col")
        if len(cols) < 8:
            continue

        # Fighter names — winner always listed first on ufcstats
        # Names may be in <p> tags with nested <a> links, or plain text
        fighter_paras = cols[1].select("p.b-fight-details__table-text")
        if len(fighter_paras) < 2:
            continue
        name_a = fighter_paras[0].get_text(strip=True)
        name_b = fighter_paras[1].get_text(strip=True)
        if not name_a or not name_b:
            continue

        # Winner determination — ufcstats always lists the winner first.
        # col[0] has a green "b-flag_style_green" anchor for the winning fighter.
        # BeautifulSoup class_ kwarg matches if the class is present (multi-class safe).
        green_flag = cols[0].find("a", class_="b-flag_style_green")
        result_col_text = cols[0].get_text(separator=" ", strip=True).lower()
        if green_flag:
            winner_name = name_a   # green flag always on first-listed (winner)
        elif any(x in result_col_text for x in ("draw", "nc", "no contest", "overturned")):
            winner_name = None
        else:
            winner_name = None     # unknown — treat conservatively

        # Method — col[7] on ufcstats event pages (e.g. "KO/TKO", "U-DEC", "S-DEC", "SUB")
        # col[8] is the round number — pass as detail so normalize_result can use it if needed
        method_text  = cols[7].get_text(strip=True) if len(cols) > 7 else ""
        method_detail = cols[8].get_text(strip=True) if len(cols) > 8 else ""

        # Weight class — col[6]
        weight_class = cols[6].get_text(strip=True) if len(cols) > 6 else "Unknown"

        # NC/draw can also appear in the method column — avoid "nc" substring (hits "punches")
        if any(x in method_text.lower() for x in ("draw", "no contest", "overturned")):
            winner_name = None

        try:
            result_type = normalize_result(method_text, method_detail)
        except ValueError:
            print(f"  WARNING: unknown method '{method_text} {method_detail}' "
                  f"in {event['name']} — skipping fight {name_a} vs {name_b}")
            continue

        a_id = resolve_id(name_a)
        b_id = resolve_id(name_b)
        winner_id = resolve_id(winner_name) if winner_name else None

        fights.append(Fight(
            date=event["date"],
            event=event["name"],
            fighter_a_id=a_id,
            fighter_b_id=b_id,
            winner_id=winner_id,
            result_type=result_type,
            weight_class=weight_class,
            event_sequence=sequence,
        ))

    return fights


def get_upcoming_events() -> list:
    """Returns list of {name, url, date} for announced upcoming UFC events."""
    url = "http://ufcstats.com/statistics/events/upcoming?page=all"
    print("Fetching upcoming events from ufcstats.com...")
    soup = _get(url)

    events = []
    for row in soup.select("tr.b-statistics__table-row"):
        link = row.select_one("a.b-link")
        if not link:
            continue
        date_span = row.select_one("span.b-statistics__date")
        if not date_span:
            continue
        try:
            event_date = datetime.strptime(date_span.text.strip(), "%B %d, %Y").date()
        except ValueError:
            continue
        events.append({
            "name": link.text.strip(),
            "url":  link["href"],
            "date": event_date,
        })

    events.sort(key=lambda e: e["date"])
    print(f"Found {len(events)} upcoming events")
    return events


def scrape_event_details(event: dict) -> dict:
    """Scrapes location and announced card from an event page (works for upcoming and past)."""
    soup = _get(event["url"])

    location = ""
    for li in soup.select("li.b-list__box-list-item"):
        txt = li.get_text(" ", strip=True)
        if "Location:" in txt:
            location = txt.replace("Location:", "").strip()
            break

    card = []
    for row in soup.select("tr.b-fight-details__table-row[data-link]"):
        cols = row.select("td.b-fight-details__table-col")
        if len(cols) < 2:
            continue
        paras = cols[1].select("p.b-fight-details__table-text")
        if len(paras) < 2:
            continue
        name_a = paras[0].get_text(strip=True)
        name_b = paras[1].get_text(strip=True)
        if name_a and name_b and name_a != name_b:
            card.append({"fighter_a": name_a, "fighter_b": name_b})

    return {"location": location, "card": card}


def scrape_events(events: list, checkpoint_cb=None) -> list:
    """
    Scrape a list of events and return all Fight objects.
    Calls checkpoint_cb(fights_so_far, last_event) every 50 events if provided.
    """
    all_fights = []
    for i, event in enumerate(events):
        print(f"[{i+1}/{len(events)}] {event['name']} ({event['date']})", end="  ")
        try:
            fights = scrape_event(event)
            print(f"{len(fights)} fights")
            all_fights.extend(fights)
        except Exception as e:
            print(f"ERROR: {e} — skipping event")

        if checkpoint_cb and (i + 1) % 50 == 0:
            checkpoint_cb(all_fights, event)

        time.sleep(REQUEST_DELAY)

    return all_fights
