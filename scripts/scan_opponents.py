#!/usr/bin/env python3
"""
scan_opponents.py - run by the "Debug a schedule page" workflow (url:
"opponents"), since school sites can't be reached from everywhere.

For players whose school hasn't posted its new season yet: reads last
season's opponents (their website links) from the school's schedule page,
opens each opponent's new-season Sidearm schedule and prints any game
against one of our schools - an early look before our school posts.
Each opponent's men's volleyball page is found from its homepage menu
(names vary: /sports/mens-volleyball/, /sports/mvb/, ...). PrestoSports
sites block GitHub, so those usually end up listed as unchecked.
"""

import os
import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fetch_sidearm_schedules import HEADERS  # noqa: E402
from presto_parser import parse_presto_schedule  # noqa: E402
from sidearm_parser import parse_sidearm_schedule  # noqa: E402

SEASON = "2027"
PRESTO_SEASON = "2026-27"
# Schools name their men's volleyball pages differently (Fort Valley State:
# /sports/mvb/). The opponent's homepage menu is checked first, then these.
MVB_SLUGS = ["mens-volleyball", "mvb", "mvball", "m-volley", "mvolley", "mens-volley", "m-vball"]
SLUG_RE = re.compile(r"/sports/([^/?#]+)/")
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


def mvb_slugs(site):
    """Men's volleyball page names linked from the opponent's homepage menu."""
    found = []
    try:
        soup = BeautifulSoup(get(site).text, "html.parser")
    except Exception:
        return MVB_SLUGS
    for a in soup.select("a[href]"):
        m = SLUG_RE.search(a["href"])
        text = a.get_text(" ", strip=True).lower()
        if m and "volley" in (m.group(1) + " " + text) and not re.search(r"wom|\bw-?v|wvb", m.group(1) + " " + text) \
                and ("men" in text or m.group(1) in MVB_SLUGS) and m.group(1) not in found:
            found.append(m.group(1))
    return found + [s for s in MVB_SLUGS if s not in found]


def new_season_schedule(site):
    """(url, games) for the opponent's new-season schedule, or (reason, None)."""
    last = "no men's volleyball page found"
    for slug in mvb_slugs(site):
        for url, parse in ((f"{site}/sports/{slug}/schedule/{SEASON}", "sidearm"),
                           (f"{site}/sports/{slug}/{PRESTO_SEASON}/schedule", "presto")):
            try:
                r = get(url)
            except Exception as e:
                last = str(e)[:60]
                continue
            if not r.ok:
                last = f"{r.status_code} at {url}"
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.get_text() if soup.title else ""
            # Only trust a page that says it's the new season (a redirect to
            # last season's page would otherwise look like a posted schedule).
            if not any(x in title or x in r.url for x in (f"/schedule/{SEASON}", SEASON, PRESTO_SEASON)):
                last = f"not posted yet ({r.url})"
                continue
            games = (parse_sidearm_schedule(soup.get_text("\n")) if parse == "sidearm"
                     else parse_presto_schedule(r.text))
            return r.url, games
    return last, None


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
            if site not in checked:
                checked[site] = new_season_schedule(site)
            status, games = checked[site]
            if games is None:
                print(f"  UNCHECKED {name} ({site}) - {status}")
                continue
            hits = [g for g in games
                    if any(re.search(rf"\b{re.escape(a)}\b", (g['opponent'] or '').lower()) for a in aliases)]
            print(f"  {'HIT' if hits else 'ok '} {name} ({status}) - {len(games)} games posted")
            for g in hits:
                print(f"      -> {g['date']} {g['time'] or ''} {g['home_away']} {g['opponent']} | {g['location']}")


if __name__ == "__main__":
    main()
