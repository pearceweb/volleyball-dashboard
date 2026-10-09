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
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from build_calendars import write_calendars
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


# ---------------------------------------------------------------------------
# TIME ZONES: schools list times in their own zone unless a game is
# labelled otherwise (North Park's "Noon ET" at Calvin; Presto's
# "7:00 PM CST"). Add each new school here - unknown schools fall back to
# Central with a warning.
# ---------------------------------------------------------------------------
SCHOOL_TZ = {
    "Long Island University": "America/New_York",
    "UW-Stevens Point": "America/Chicago",
    "Park University (Gilbert)": "America/Phoenix",  # Arizona - no DST
    "Rockhurst University": "America/Chicago",
    "Vassar College": "America/New_York",
    "North Park University": "America/Chicago",
    "Mercy University": "America/New_York",
    "Central State University": "America/New_York",
    "Olivet Nazarene University": "America/Chicago",
    "Orange Coast College": "America/Los_Angeles",
}
DEFAULT_TZ = "America/Chicago"

# Each team's men's volleyball Instagram handle (no "@"), linked at the top
# of the player's page. None = no account; the page shows no link.
SCHOOL_INSTAGRAM = {
    "Long Island University": "liusharksmvb",
    "UW-Stevens Point": "uwspmvb",
    "Park University (Gilbert)": "parkugilbert_mvb",
    "Rockhurst University": "rockhurstmvb",
    "Vassar College": "vassarmvb",
    "North Park University": "npumensvb",
    "Mercy University": "mercymvbteam",
    "Central State University": "centralstatemvb",
    "Olivet Nazarene University": "olivetmvb",
    "Orange Coast College": "occmvball",
}
TZ_BY_LETTER = {
    "E": "America/New_York",
    "C": "America/Chicago",
    "M": "America/Denver",
    "P": "America/Los_Angeles",
}
TIME_RE = re.compile(
    r"^\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\s*(?:([ECMP])[SD]?T)?\s*$", re.IGNORECASE)
missing_tz_schools = set()


AT_PLACE_RE = re.compile(r"^(.*?)\s+@\s+(.+)$")


def clean_location(loc):
    """
    Schools write extra info around the city, in either order:
    Sidearm "Springfield, MA | Springfield", Presto "McHie Arena |
    Bourbonnais, Ill.". Keep the part that looks like "City, State".
    """
    parts = [p.strip() for p in (loc or "").split("|") if p.strip()]
    return next((p for p in parts if "," in p), parts[0] if parts else None)


def split_time(text):
    """'7:00 PM CST' -> ('7:00 PM', 'C'); anything else -> (None, None)."""
    m = TIME_RE.match(text or "")
    if not m:
        return None, None
    hour, minute, ap, letter = m.groups()
    return f"{int(hour)}:{minute or '00'} {ap.upper()}M", (letter.upper() if letter else None)


def resolve_tz(school, label):
    """label is a zone letter/abbreviation like 'E' or 'ET', or None."""
    if label:
        return TZ_BY_LETTER.get(label[0].upper(), DEFAULT_TZ)
    if school not in SCHOOL_TZ:
        missing_tz_schools.add(school)
    return SCHOOL_TZ.get(school, DEFAULT_TZ)


def start_utc(date_iso, time_text, tz):
    """Exact start as a UTC ISO string, or None if date/time unknown."""
    t, _ = split_time(time_text)
    if not (date_iso and t):
        return None
    local = datetime.strptime(f"{date_iso} {t}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ZoneInfo(tz))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_sidearm(entry):
    year = resolve_year(entry["url"], "sidearm")
    out = []
    for g in entry.get("games", []):
        date_iso = parse_iso_date(g.get("date"), year)
        tz = resolve_tz(entry["school"], g.get("tz"))
        out.append({
            "player": entry["player"],
            "school": entry["school"],
            "date_iso": date_iso,
            "date_display": g.get("date"),
            "time": g.get("time"),
            "tz": tz,
            "start_utc": start_utc(date_iso, g.get("time"), tz),
            "home_away": g.get("home_away", "neutral"),
            "opponent": g.get("opponent"),
            "location": clean_location(g.get("location")),
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
        date_iso = parse_iso_date(g.get("date"), year)
        # Presto puts upcoming game times in the status column
        # ("7:00 PM CST"); pull them out into time + zone.
        status = g.get("status")
        time, label = g.get("time"), None
        if not time:
            time, label = split_time(status)
            if time:
                status = None
        tz = resolve_tz(entry["school"], label)
        # Presto tournament games read "Hastings @ Sioux City, Iowa" (or
        # "@ Tournament" when the site isn't named) - a neutral-site game.
        opponent, home_away = g.get("opponent"), g.get("home_away", "neutral")
        location = clean_location(g.get("location"))
        m = AT_PLACE_RE.match(opponent or "")
        if m:
            opponent, place = m.group(1).strip(), m.group(2).strip()
            home_away = "neutral"
            if place.lower() != "tournament":
                location = place
        out.append({
            "player": entry["player"],
            "school": entry["school"],
            "date_iso": date_iso,
            "date_display": g.get("date"),
            "time": time,
            "tz": tz,
            "start_utc": start_utc(date_iso, time, tz),
            "home_away": home_away,
            "opponent": opponent,
            "location": location,
            "result": g.get("result"),
            "sets": g.get("sets"),
            "status": status,
            "streaming_label": None,
            # Presto links are often relative ("/links/abc") - make them
            # absolute against the school's site or they 404 on our page.
            "streaming_url": urljoin(entry["url"], g["video_url"]) if g.get("video_url") else None,
            "platform": "presto",
        })
    return out


# ---------------------------------------------------------------------------
# MN SELECT MATCHUPS: games where a player's team faces another player's
# team. Opponent names vary by school ("Central State" vs "Central State
# University"), so list the names each school goes by. Matching is on the
# START of the opponent name, so "St. Joseph's University Long Island" is
# not LIU and "Mercyhurst" is not Mercy. Add new schools here.
# ---------------------------------------------------------------------------
SCHOOL_ALIASES = {
    "Long Island University": ["long island university", "liu"],
    "UW-Stevens Point": ["uw-stevens point", "uw stevens point", "wisconsin-stevens point", "uwsp"],
    "Park University (Gilbert)": ["park university gilbert", "park university (gilbert)", "park gilbert",
                                  "park (gilbert)", "park university-gilbert"],
    "Rockhurst University": ["rockhurst"],
    "Vassar College": ["vassar"],
    "North Park University": ["north park"],
    "Mercy University": ["mercy university", "mercy college", "mercy"],
    "Central State University": ["central state"],
    "Olivet Nazarene University": ["olivet nazarene", "olivet"],
    "Orange Coast College": ["orange coast"],
}


def season_of(date_iso):
    """'2027-02-14' -> 2026: a season runs July-June, named by its fall year."""
    year, month = int(date_iso[:4]), int(date_iso[5:7])
    return year if month >= 7 else year - 1


def load_manual_games(players, fetched):
    """
    Games the schools' schedule pages don't list (fall scrimmages etc.),
    added by hand to manual_games.json. Merged in on every build so the
    scheduled jobs never wipe them. Skipped once the school's own schedule
    shows a game that day, so nothing appears twice. Entries marked
    "until_schedule_posted" (a season copied from a school's teaser graphic)
    are all dropped once the school's own schedule has any game that season.
    """
    try:
        with open("manual_games.json", encoding="utf-8") as f:
            entries = json.load(f)
    except FileNotFoundError:
        return []
    player_for = {p["school"]: p["player"] for p in players}
    fetched_days = {(g["school"], g["date_iso"]) for g in fetched}
    fetched_seasons = {(g["school"], season_of(g["date_iso"])) for g in fetched if g["date_iso"]}
    out = []
    for g in entries:
        school = g["school"]
        if school not in player_for:
            print(f"WARNING: manual game for unknown school {school!r} - skipped")
            continue
        if g.get("until_schedule_posted") and (school, season_of(g["date"])) in fetched_seasons:
            continue
        if (school, g["date"]) in fetched_days:
            print(f"Manual game {school} {g['date']} now on the school's schedule - skipped")
            continue
        tz = resolve_tz(school, None)
        out.append({
            "player": player_for[school],
            "school": school,
            "date_iso": g["date"],
            "date_display": datetime.strptime(g["date"], "%Y-%m-%d").strftime("%b %-d"),
            "time": g.get("time"),
            "tz": tz,
            "start_utc": start_utc(g["date"], g.get("time"), tz),
            "home_away": g.get("home_away", "neutral"),
            "opponent": g.get("opponent"),
            "location": g.get("location"),
            "result": g.get("result"),
            "sets": g.get("sets"),
            "status": None,
            "streaming_label": None,
            "streaming_url": g.get("watch_url"),
            "platform": "manual",
        })
        if g.get("partial"):
            # A few games found on opponents' schedules before our school
            # posts its own - the page labels them as a sneak peek.
            out[-1]["partial"] = True
            out[-1]["source"] = g.get("source")
    return out


def _norm(name):
    name = re.sub(r"^(No\.\s*\d+|#\d+|#RV)\s+", "", (name or "").strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name.lower().replace(".", ""))


def tag_matchups(all_games, players):
    """Adds g["matchup_with"] = [{"player", "school"}, ...] (or [])."""
    by_school = {}
    for p in players:
        by_school.setdefault(p["school"], []).append(p)
    for g in all_games:
        opp = _norm(g.get("opponent"))
        g["matchup_with"] = [
            {"player": p["player"], "school": p["school"]}
            for school, ps in by_school.items() if school != g["school"]
            for alias in SCHOOL_ALIASES.get(school, [_norm(school)])
            if re.match(rf"{re.escape(alias)}(\b|$)", opp)
            for p in ps
        ]
        # an alias list can match twice (e.g. "mercy university" and "mercy")
        g["matchup_with"] = [dict(t) for t in {tuple(m.items()) for m in g["matchup_with"]}]


def main():
    all_games = []
    unresolved_dates = []
    # Every configured player, including ones with no games yet (e.g. a
    # school that hasn't posted its schedule) so the page can still list them.
    players = []

    try:
        with open("sidearm_games.json", encoding="utf-8") as f:
            sidearm_data = json.load(f)
        for entry in sidearm_data:
            all_games.extend(normalize_sidearm(entry))
            players.append({"player": entry["player"], "school": entry["school"]})
    except FileNotFoundError:
        print("sidearm_games.json not found - skipping (run fetch_sidearm_schedules.py first)")

    try:
        with open("presto_games.json", encoding="utf-8") as f:
            presto_data = json.load(f)
        for entry in presto_data:
            all_games.extend(normalize_presto(entry))
            players.append({"player": entry["player"], "school": entry["school"]})
    except FileNotFoundError:
        print("presto_games.json not found - skipping (run fetch_presto_schedules.py first)")

    manual = load_manual_games(players, all_games)
    # A school with hand-added games in a newer season than its own schedule
    # page (e.g. UWSP's teaser before its page is updated): drop the old
    # season's games so they're never shown as the current player's.
    newest_manual = {}
    for g in manual:
        newest_manual[g["school"]] = max(newest_manual.get(g["school"], 0), season_of(g["date_iso"]))
    all_games = [g for g in all_games
                 if not (g["school"] in newest_manual and g["date_iso"]
                         and season_of(g["date_iso"]) < newest_manual[g["school"]])]
    all_games.extend(manual)

    for g in all_games:
        if g["date_iso"] is None and g["date_display"]:
            unresolved_dates.append(f"{g['school']} - {g['date_display']}")

    # Sort: games with a resolved date first (chronological), undated last
    all_games.sort(key=lambda g: (g["date_iso"] is None, g["date_iso"] or ""))
    tag_matchups(all_games, players)

    with open("unified_schedule.json", "w", encoding="utf-8") as f:
        json.dump(all_games, f, indent=2)

    print(f"Wrote {len(all_games)} games to unified_schedule.json")
    if missing_tz_schools:
        print(f"WARNING: no time zone set for {sorted(missing_tz_schools)} - "
              f"assumed Central. Add them to SCHOOL_TZ.")

    # Subscribable calendar feeds (calendars/*.ics); the page links to each
    # player's feed via the "calendar" path in players.json.
    cal_paths = write_calendars(all_games, players)
    for p in players:
        p["calendar"] = cal_paths.get(p["player"])
        handle = SCHOOL_INSTAGRAM.get(p["school"])
        if handle:
            p["instagram"] = f"https://www.instagram.com/{handle}/"
    print(f"Wrote {len(cal_paths) + 1} calendar feeds to calendars/")

    with open("players.json", "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2)
    print(f"Wrote {len(players)} players to players.json")
    if unresolved_dates:
        print(f"\n{len(unresolved_dates)} games had a date but couldn't resolve a year "
              f"(check the URL year patterns):")
        for d in unresolved_dates[:10]:
            print(f"  - {d}")


if __name__ == "__main__":
    main()
