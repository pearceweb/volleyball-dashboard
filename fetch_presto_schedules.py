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
import time

import requests

from presto_parser import parse_presto_schedule

# ---------------------------------------------------------------------------
# CONFIG - one entry per PrestoSports-powered school.
# `year` is the schedule page's season segment (e.g. .../2025-26/schedule).
# Update this each year once the new season's page goes live.
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
    )
}


def fetch_and_parse(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return parse_presto_schedule(resp.text)


def main():
    all_results = []
    for entry in SCHOOLS:
        print(f"Fetching {entry['school']} ({entry['player']})...")
        try:
            games = fetch_and_parse(entry["url"])
            print(f"  -> parsed {len(games)} games")
            all_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": entry["url"],
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
        time.sleep(1)

    with open("presto_games.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved to presto_games.json")


if __name__ == "__main__":
    main()
