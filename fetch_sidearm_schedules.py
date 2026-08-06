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
import time

import requests
from bs4 import BeautifulSoup

from sidearm_parser import parse_sidearm_schedule

# ---------------------------------------------------------------------------
# CONFIG - one entry per Sidearm-powered school.
# `year` is the schedule page's year segment (e.g. .../schedule/2026).
# Update this each year once the new season's page goes live.
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
        "url": "https://www.vassarathletics.com/sports/mens-volleyball/schedule/2026",
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
        time.sleep(1)  # be polite between requests

    with open("sidearm_games.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved to sidearm_games.json")


if __name__ == "__main__":
    main()
