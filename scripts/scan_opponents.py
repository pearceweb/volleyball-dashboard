#!/usr/bin/env python3
"""
scan_opponents.py - run by the "Debug a schedule page" workflow (url:
"opponents"), since school sites can't be reached from everywhere.

For players whose school hasn't posted its new season yet: reads last
season's opponents (their website links) from the school's schedule page,
opens each opponent's new-season Sidearm schedule and prints any game
against one of our schools - an early look before our school posts.
Opponents on PrestoSports or other platforms are listed as unchecked.
"""

import os
import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fetch_sidearm_schedules import HEADERS  # noqa: E402
from sidearm_parser import parse_sidearm_schedule  # noqa: E402

SEASON = "2027"
# Our schools to look for: schedule page of last season + names opponents use.
TARGETS = {
    "Long Island University": (
        "https://www.liuathletics.com/sports/mens-volleyball/schedule/2026",
        ["long island university", "liu"]),
    "Central State University": (
        "https://maraudersports.com/sports/mens-volleyball/schedule/2026",
        ["central state"]),
    "Park University (Gilbert)": (
        "https://gilbert.parkathletics.com/sports/mens-volleyball/schedule/2026",
        ["park"]),  # loose on purpose: Park's two campuses are told apart by hand
}
SKIP_HOSTS = re.compile(r"facebook|twitter|x\.com|instagram|youtube|tiktok|sidearm|"
                        r"flosports|espn|hudl|google|apple\.com|stats|prestosports|"
                        r"boxcast|vimeo|livestream|ncaa|naia|wmt\.digital")


def get(url):
    return requests.get(url, headers=HEADERS, timeout=30)


def opponent_sites(schedule_url):
    """Opponent website roots linked from a Sidearm schedule page."""
    soup = BeautifulSoup(get(schedule_url).text, "html.parser")
    own = urlparse(schedule_url).hostname
    links = soup.select('[class*="opponent-name"] a[href]') or soup.select("a[href]")
    sites = {}
    for a in links:
        u = urlparse(a["href"])
        if u.scheme.startswith("http") and u.hostname and u.hostname != own \
                and not SKIP_HOSTS.search(u.hostname):
            sites.setdefault(f"{u.scheme}://{u.hostname}", a.get_text(" ", strip=True))
    return sites


def main():
    checked = {}
    for school, (url, aliases) in TARGETS.items():
        print(f"\n===== {school}")
        try:
            sites = opponent_sites(url)
        except Exception as e:
            print(f"  could not read {url}: {e}")
            continue
        print(f"  {len(sites)} opponent sites linked")
        for site, name in sorted(sites.items()):
            sched = f"{site}/sports/mens-volleyball/schedule/{SEASON}"
            if sched not in checked:
                try:
                    r = get(sched)
                    games = (parse_sidearm_schedule(BeautifulSoup(r.text, "html.parser").get_text("\n"))
                             if r.ok and f"/schedule/{SEASON}" in r.url else None)
                    checked[sched] = (r.status_code, games)
                except Exception as e:
                    checked[sched] = (str(e)[:60], None)
            status, games = checked[sched]
            if games is None:
                print(f"  UNCHECKED {name} ({site}) - {status}")
                continue
            hits = [g for g in games
                    if any(re.search(rf"\b{re.escape(a)}\b", (g['opponent'] or '').lower()) for a in aliases)]
            print(f"  {'HIT' if hits else 'ok '} {name} ({site}) - {len(games)} games posted")
            for g in hits:
                print(f"      -> {g['date']} {g['time'] or ''} {g['home_away']} {g['opponent']} | {g['location']}")


if __name__ == "__main__":
    main()
