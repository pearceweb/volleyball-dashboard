#!/usr/bin/env python3
"""
fetch_sidearm_schedules.py

Fetches and parses Sidearm Sports men's volleyball schedules for our
8 Sidearm-powered schools. Run this on your Mac (needs internet access,
which this sandbox doesn't have).

Usage:
    pip3 install requests beautifulsoup4
    python3 fetch_sidearm_schedules.py

Output: prints parsed JSON for each school, and saves to sidearm_games.json
"""

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from sidearm_parser import parse_sidearm_schedule

# ---------------------------------------------------------------------------
# CONFIG - one entry per Sidearm-powered school.
# `year` is the schedule page's year segment (e.g. .../schedule/2026).
# You no longer need to bump this by hand: each run also checks the next
# year's page and moves forward automatically once the school posts a real
# new schedule there (see resolve_current_season). Bumping it is still fine
# - it just saves one extra request per run.
# ---------------------------------------------------------------------------
SCHOOLS = [
    {
        "player": "Drew Demarais",
        "school": "Long Island University",
        "url": "https://www.liuathletics.com/sports/mens-volleyball/schedule/2026",
    },
    {
        "player": "Ben DeVos",
        "school": "UW-Stevens Point",
        "url": "https://athletics.uwsp.edu/sports/mens-volleyball/schedule/2026",
    },
    {
        "player": "Henry Hudson",
        "school": "Park University (Gilbert)",
        "url": "https://gilbert.parkathletics.com/sports/mens-volleyball/schedule/2026",
    },
    {
        "player": "Ryan Michalak",
        "school": "Rockhurst University",
        "url": "https://rockhursthawks.com/sports/mens-volleyball/schedule/2026",
    },
    {
        "player": "Colin Nathan",
        "school": "Vassar College",
        "url": "https://www.vassarathletics.com/sports/mens-volleyball/schedule/2027",
    },
    {
        "player": "Colson Pearce",
        "school": "North Park University",
        "url": "https://athletics.northpark.edu/sports/mens-volleyball/schedule/2027",
    },
    {
        "player": "Treysen Cornillez",
        "school": "Mercy University",
        # Program is brand new (first season 2026-27); no schedule page exists
        # yet at any year. This base URL (no year) should start working the
        # moment they publish their first schedule - worth rechecking monthly.
        "url": "https://mercyathletics.com/sports/mens-volleyball/schedule",
    },
    {
        "player": "Kaleb Mhiripiri",
        "school": "Central State University",
        "url": "https://maraudersports.com/sports/mens-volleyball/schedule/2026",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_and_parse(url):
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n")
            return parse_sidearm_schedule(text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))  # 5s, then 10s before retrying
    raise last_error


YEAR_URL_RE = re.compile(r"^(.*/schedule/)(\d{4})/?$")
MAX_YEARS_AHEAD = 2  # safety cap on how far we'll walk forward in one run


def _signature(games):
    return [(g.get("date"), g.get("opponent")) for g in games]


def resolve_current_season(url, games):
    """
    Walk forward from the configured year while the next year's page has
    its own schedule. A school that hasn't posted next season yet still
    serves a page at /schedule/<next year>, but it just repeats the current
    season's games - so we only advance when the next page has games AND
    they differ from what we already have.
    """
    m = YEAR_URL_RE.match(url)
    if not m:
        return url, games  # no year in the URL (e.g. Mercy) - nothing to advance
    base, year = m.group(1), int(m.group(2))
    for _ in range(MAX_YEARS_AHEAD):
        next_url = f"{base}{year + 1}"
        try:
            next_games = fetch_and_parse(next_url)
        except Exception:
            break
        if not next_games or _signature(next_games) == _signature(games):
            break
        url, games, year = next_url, next_games, year + 1
        time.sleep(1)
    return url, games


def load_previous_urls():
    try:
        with open("sidearm_games.json", encoding="utf-8") as f:
            return {e["player"]: e["url"] for e in json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def main():
    previous_urls = load_previous_urls()
    season_updates = []
    all_results = []
    for entry in SCHOOLS:
        print(f"Fetching {entry['school']} ({entry['player']})...")
        try:
            games = fetch_and_parse(entry["url"])
            url, games = resolve_current_season(entry["url"], games)
            if url != entry["url"]:
                print(f"  -> newer season found: {url}")
            prev = previous_urls.get(entry["player"])
            if prev and prev != url:
                season_updates.append(
                    f"{entry['player']} - {entry['school']}: new schedule posted "
                    f"({len(games)} games). Now using {url}"
                )
            print(f"  -> parsed {len(games)} games")
            all_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": url,
                "games": games,
                "error": None,
            })
        except Exception as e:
            print(f"  -> ERROR: {e}")
            all_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": entry["url"],
                "games": [],
                "error": str(e),
            })
        time.sleep(1)  # be polite between requests

    with open("sidearm_games.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved to sidearm_games.json")

    # The workflow emails this file's contents when it's non-empty.
    with open("season_updates.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(season_updates))
    if season_updates:
        print("\nNEW SEASONS DETECTED:")
        for u in season_updates:
            print(f"  - {u}")


if __name__ == "__main__":
    main()
