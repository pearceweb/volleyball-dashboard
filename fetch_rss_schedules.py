#!/usr/bin/env python3
"""
fetch_rss_schedules.py

Fetches and parses PrestoSports RSS composite feeds for our 2
PrestoSports-powered schools (Olivet Nazarene, Orange Coast). This is an
alternative to fetch_presto_schedules.py (which scrapes the HTML table) -
the RSS feed is real structured XML built specifically for syndication,
and it's worth testing whether it's also exempt from the IP block that
hits the regular HTML page from GitHub Actions' IP ranges.

Usage:
    pip3 install requests
    python3 fetch_rss_schedules.py

Output: prints progress, saves to presto_games.json (same output file
and shape as fetch_presto_schedules.py, so build_unified_schedule.py
doesn't need to know which method produced the data).
"""

import json
import time

import requests

from rss_parser import parse_rss_schedule

SCHOOLS = [
    {
        "player": "Ethan Jordheim",
        "school": "Olivet Nazarene University",
        "url": "https://www.onutigers.com/sports/mvball/composite?print=rss",
    },
    # Orange Coast's RSS composite feed is stale (stuck around 2015 -
    # the school's site admin never added recent seasons to it, per
    # PrestoSports' own docs that say this requires manual curation on
    # their end). So Connor's data stays on the manual HTML-table method
    # (fetch_presto_schedules.py, run locally) instead of RSS here.
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_and_parse(url):
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return parse_rss_schedule(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise last_error


def main():
    fresh_results = []
    for entry in SCHOOLS:
        print(f"Fetching {entry['school']} ({entry['player']})...")
        try:
            games = fetch_and_parse(entry["url"])
            print(f"  -> parsed {len(games)} games")
            fresh_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": entry["url"],
                "games": games,
                "error": None,
            })
        except Exception as e:
            print(f"  -> ERROR: {e}")
            fresh_results.append({
                "player": entry["player"],
                "school": entry["school"],
                "url": entry["url"],
                "games": [],
                "error": str(e),
            })
        time.sleep(1)

    # Merge into the existing presto_games.json rather than overwriting it -
    # this file may also contain schools updated by the manual HTML-table
    # method (fetch_presto_schedules.py), and we don't want to wipe those
    # out just because this run only covers a subset of schools.
    try:
        with open("presto_games.json", encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []

    by_school = {e["school"]: e for e in existing}
    for fresh in fresh_results:
        by_school[fresh["school"]] = fresh

    merged = list(by_school.values())

    with open("presto_games.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    print("\nSaved to presto_games.json")


if __name__ == "__main__":
    main()
