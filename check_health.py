#!/usr/bin/env python3
"""
check_health.py
Last updated: 2026-08-05

Compares the just-fetched sidearm_games.json / presto_games.json against
snapshots of the PREVIOUS run's data (sidearm_games_previous.json /
presto_games_previous.json - copied by the workflow before re-fetching) to
catch a scraper silently breaking:
  - a school that had games before now returns 0
  - a school's fetch recorded an explicit error
  - a school's game count drops sharply for no obvious reason

Writes any problems found to health_alerts.txt (one per line, empty file
if everything looks fine) and exits non-zero if there are alerts, so the
workflow step running this can react to it.

Run locally to test:
    python3 check_health.py
"""

import json
import sys

DROP_THRESHOLD = 0.5  # flag if game count drops by 50%+ vs last run
MIN_PREVIOUS_FOR_DROP_CHECK = 5  # don't flag drops on schools with tiny counts to begin with


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def counts_by_school(data):
    return {
        entry["school"]: {"count": len(entry.get("games", [])), "error": entry.get("error")}
        for entry in data
    }


def check(current_path, previous_path, alerts):
    current = counts_by_school(load(current_path))
    previous = counts_by_school(load(previous_path))

    for school, info in current.items():
        if info["error"]:
            alerts.append(f"{school}: fetch error - {info['error']}")
            continue

        prev_info = previous.get(school)
        if prev_info is None:
            continue  # first time seeing this school - nothing to compare yet

        prev_count = prev_info["count"]
        cur_count = info["count"]

        if cur_count == 0 and prev_count > 0:
            alerts.append(f"{school}: went from {prev_count} games to 0 games")
        elif prev_count >= MIN_PREVIOUS_FOR_DROP_CHECK:
            drop = (prev_count - cur_count) / prev_count
            if drop >= DROP_THRESHOLD:
                alerts.append(f"{school}: game count dropped from {prev_count} to {cur_count}")


def main():
    alerts = []
    check("sidearm_games.json", "sidearm_games_previous.json", alerts)
    check("presto_games.json", "presto_games_previous.json", alerts)

    with open("health_alerts.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(alerts))

    if alerts:
        print("HEALTH CHECK FOUND ISSUES:")
        for a in alerts:
            print(f"  - {a}")
        sys.exit(1)
    else:
        print("Health check passed - no issues found.")


if __name__ == "__main__":
    main()
