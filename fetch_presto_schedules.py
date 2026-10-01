#!/usr/bin/env python3
"""
fetch_presto_schedules.py

Fetches and parses PrestoSports men's volleyball schedules for our 2
PrestoSports-powered schools (Olivet Nazarene, Orange Coast). Run this on
your Mac (needs internet access, which the sandbox this was built in
doesn't have).

Usage:
    pip3 install requests beautifulsoup4
    python3 fetch_presto_schedules.py

Output: prints progress, saves to presto_games.json
"""

import json
import re
import time

import requests

from presto_parser import parse_presto_schedule

# ---------------------------------------------------------------------------
# CONFIG - one entry per PrestoSports-powered school.
# `year` is the schedule page's season segment (e.g. .../2025-26/schedule).
# No need to bump it by hand: each run checks the next season's page and
# moves forward once the school posts it (see resolve_current_season).
# scripts/local_presto_update.sh runs this daily on the Mac.
# ---------------------------------------------------------------------------
SCHOOLS = [
    {
        "player": "Ethan Jordheim",
        "school": "Olivet Nazarene University",
        "url": "https://www.onutigers.com/sports/mvball/2026-27/schedule",
    },
    {
        "player": "Connor Voss",
        "school": "Orange Coast College",
        "url": "https://www.occpirateathletics.com/sports/mvball/2025-26/schedule",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Referer": "https://www.google.com/",
}


def fetch_and_parse(url):
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return parse_presto_schedule(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))  # 5s, then 10s before retrying
    raise last_error


SEASON_URL_RE = re.compile(r"^(.*/)(\d{4})-(\d{2})(/schedule/?)$")
MAX_SEASONS_AHEAD = 2  # safety cap on how far we'll walk forward in one run


def _next_season_url(url):
    m = SEASON_URL_RE.match(url)
    if not m:
        return None
    first = int(m.group(2)) + 1
    return f"{m.group(1)}{first}-{str(first + 1)[-2:]}{m.group(4)}"


def resolve_current_season(url, games):
    """
    Walk forward while the next season's schedule page exists and has games.
    Presto returns 404 for a season the school hasn't set up yet, so a
    single quick request tells us whether it's been posted.
    """
    for _ in range(MAX_SEASONS_AHEAD):
        next_url = _next_season_url(url)
        if not next_url:
            break
        try:
            resp = requests.get(next_url, headers=HEADERS, timeout=30)
        except requests.exceptions.RequestException:
            break
        if resp.status_code != 200:
            break
        next_games = parse_presto_schedule(resp.text)
        if not next_games:
            break  # page exists but no games entered yet
        url, games = next_url, next_games
        time.sleep(1)
    return url, games


def load_previous():
    """Last run's entries, keyed by player."""
    try:
        with open("presto_games.json", encoding="utf-8") as f:
            return {e["player"]: e for e in json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def main():
    previous = load_previous()
    season_updates = []
    new_errors = []
    all_results = []
    for entry in SCHOOLS:
        print(f"Fetching {entry['school']} ({entry['player']})...")
        # Start from last run's URL if it's already moved past the config.
        start_url = max(entry["url"], previous.get(entry["player"], {}).get("url") or "")
        try:
            games = fetch_and_parse(start_url)
            had = len(previous.get(entry["player"], {}).get("games", []))
            if not games and had:
                # A page that suddenly has no games is almost always the site
                # being down or changed (e.g. Orange Coast's domain lapsing to
                # a parking page on 2026-09-30), not a real empty schedule.
                # Treat it as an error so last run's games are kept.
                raise ValueError(f"page returned 0 games (had {had} last run) - site down or changed?")
            url, games = resolve_current_season(start_url, games)
            if url != start_url:
                print(f"  -> newer season found: {url}")
            prev = previous.get(entry["player"], {}).get("url")
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
            # Keep last run's games so a temporary outage doesn't wipe the
            # schedule; the error is still recorded for the health check.
            prev = previous.get(entry["player"], {})
            kept = prev.get("games", [])
            print(f"  -> ERROR: {e} (keeping {len(kept)} games from last run)")
            if not prev.get("error"):
                new_errors.append(f"{entry['player']} - {entry['school']}: {e}")
            all_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": prev.get("url", entry["url"]),
                "games": kept,
                "error": str(e),
            })
        time.sleep(1)

    with open("presto_games.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved to presto_games.json")

    with open("presto_season_updates.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(season_updates))
    # New problems (not already flagged last run) - the Mac job emails these.
    with open("presto_alerts.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(new_errors))

    if season_updates:
        print("\nNEW SEASONS DETECTED:")
        for u in season_updates:
            print(f"  - {u}")


if __name__ == "__main__":
    main()
