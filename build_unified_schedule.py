#!/usr/bin/env python3
"""
build_unified_schedule.py
Last updated: 2026-07-11

Merges the two scraper outputs (sidearm_games.json, presto_games.json) into
a single, normalized, date-sorted schedule: unified_schedule.json.

Run this AFTER both fetch_sidearm_schedules.py and fetch_presto_schedules.py
have produced their JSON files.

Usage:
    python3 build_unified_schedule.py

WHY A SEPARATE STEP: the two scrapers hit very different page layouts
(Sidearm's flattened text vs. PrestoSports' real HTML table) and their raw
output reflects that - different field names, different date formats, no
shared year. This script is where all of that gets reconciled into one
consistent shape a dashboard can just read and display.

NORMALIZED GAME SHAPE:
{
  "player": "Drew Demarais",
  "school": "Long Island University",
  "date_iso": "2026-01-13",       # for sorting/filtering - may be null if
                                   # the date couldn't be resolved
  "date_display": "Jan 13",
  "time": "6 p.m." | null,
  "home_away": "home" | "away" | "neutral",
  "opponent": "St. Thomas Aquinas",
  "location": "Brooklyn, N.Y. ..." | null,
  "result": "W" | "L" | null,
  "sets": "0-3" | null,
  "status": "Final" | "Canceled" | null,
  "streaming_label": "NEC Front Row" | null,   # Sidearm-style network name
  "streaming_url": "/links/..." | null,        # PrestoSports-style video link
  "platform": "sidearm" | "presto",
}

YEAR RESOLUTION: neither scraper's raw date includes a year. We derive the
season's calendar year from each school's schedule URL:
  - Sidearm URLs end in the calendar year directly (".../schedule/2026")
  - PrestoSports URLs use an academic-year folder (".../2025-26/schedule");
    men's volleyball is a spring sport, so we use the SECOND year (2026).
If a URL doesn't match either pattern, date_iso is left null rather than
guessing - date_display is still populated so nothing is silently dropped.
"""

import json
import re
from datetime import datetime

SIDEARM_YEAR_RE = re.compile(r"/schedule/(\d{4})/?$")
PRESTO_YEAR_RE = re.compile(r"/(\d{4})-(\d{2})/schedule/?$")


def resolve_year(url, platform):
    if platform == "sidearm":
        m = SIDEARM_YEAR_RE.search(url)
        if m:
            return int(m.group(1))
    elif platform == "presto":
        m = PRESTO_YEAR_RE.search(url)
        if m:
            first_year = int(m.group(1))
            return first_year + 1  # spring season = second half of academic year
    return None


def parse_iso_date(date_display, year):
    if not date_display:
        return None

    # RSS-sourced dates already include their own year (e.g. "Jan 22, 2026") -
    # try that shape first so we don't need a URL-based year guess at all.
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(date_display, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    if not year:
        return None
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            dt = datetime.strptime(f"{date_display} {year}", fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
    return None


def normalize_sidearm(entry):
    year = resolve_year(entry["url"], "sidearm")
    out = []
    for g in entry.get("games", []):
        out.append({
            "player": entry["player"],
            "school": entry["school"],
            "date_iso": parse_iso_date(g.get("date"), year),
            "date_display": g.get("date"),
            "time": g.get("time"),
            "home_away": g.get("home_away", "neutral"),
            "opponent": g.get("opponent"),
            "location": g.get("location"),
            "result": g.get("result"),
            "sets": g.get("sets"),
            "status": g.get("status"),
            "streaming_label": g.get("tv"),
            "streaming_url": None,
            "platform": "sidearm",
        })
    return out


def normalize_presto(entry):
    year = resolve_year(entry["url"], "presto")
    out = []
    for g in entry.get("games", []):
        out.append({
            "player": entry["player"],
            "school": entry["school"],
            "date_iso": parse_iso_date(g.get("date"), year),
            "date_display": g.get("date"),
            "time": g.get("time"),
            "home_away": g.get("home_away", "neutral"),
            "opponent": g.get("opponent"),
            "location": g.get("location"),
            "result": g.get("result"),
            "sets": g.get("sets"),
            "status": g.get("status"),
            "streaming_label": None,
            "streaming_url": g.get("video_url"),
            "platform": "presto",
        })
    return out


def main():
    all_games = []
    unresolved_dates = []

    try:
        with open("sidearm_games.json", encoding="utf-8") as f:
            sidearm_data = json.load(f)
        for entry in sidearm_data:
            all_games.extend(normalize_sidearm(entry))
    except FileNotFoundError:
        print("sidearm_games.json not found - skipping (run fetch_sidearm_schedules.py first)")

    try:
        with open("presto_games.json", encoding="utf-8") as f:
            presto_data = json.load(f)
        for entry in presto_data:
            all_games.extend(normalize_presto(entry))
    except FileNotFoundError:
        print("presto_games.json not found - skipping (run fetch_presto_schedules.py first)")

    for g in all_games:
        if g["date_iso"] is None and g["date_display"]:
            unresolved_dates.append(f"{g['school']} - {g['date_display']}")

    # Sort: games with a resolved date first (chronological), undated last
    all_games.sort(key=lambda g: (g["date_iso"] is None, g["date_iso"] or ""))

    with open("unified_schedule.json", "w", encoding="utf-8") as f:
        json.dump(all_games, f, indent=2)

    print(f"Wrote {len(all_games)} games to unified_schedule.json")
    if unresolved_dates:
        print(f"\n{len(unresolved_dates)} games had a date but couldn't resolve a year "
              f"(check the URL year patterns):")
        for d in unresolved_dates[:10]:
            print(f"  - {d}")


if __name__ == "__main__":
    main()
