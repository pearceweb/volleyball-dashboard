"""
build_calendars.py

Writes subscribable calendar feeds from the unified schedule:
  calendars/<player-slug>.ics  - one per player
  calendars/all.ics            - every player

People subscribe once (webcal://...) and their calendar app re-downloads
the file periodically, so schedule changes reach them automatically.
Called from build_unified_schedule.py after unified_schedule.json is built.

The output is deterministic (no build timestamps), so a file only changes -
and only gets committed - when the schedule itself changes.
"""

import os
import re
from datetime import date, datetime, timedelta

SITE = "https://mnselectboys.tuckerpearcecreative.com/"
CAL_DIR = "calendars"
FIXED_DTSTAMP = "20260101T000000Z"  # stable on purpose - see module docstring
MATCH_LENGTH = timedelta(hours=2)


def player_slug(player):
    return re.sub(r"[^a-z0-9]+", "-", player.lower()).strip("-")


def _escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """iCalendar lines max 75 octets; continuation lines start with a space."""
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75 if not out else 74
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def _event(g):
    side = {"home": "vs", "away": "@"}.get(g.get("home_away"), "vs")
    summary = f"{g['player']} ({g['school']}) {side} {g.get('opponent') or 'TBD'}"
    if g.get("result"):
        summary += f" - {g['result']} {g.get('sets') or ''}".rstrip()

    desc = [f"{g['player']} - {g['school']}"]
    for m in g.get("matchup_with") or []:
        desc.append(f"MN Select matchup vs {m['player']} ({m['school']})")
    if g.get("home_away") == "neutral":
        desc.append("Neutral site")
    if g.get("streaming_label"):
        desc.append(f"Watch: {g['streaming_label']}")
    if g.get("streaming_url"):
        desc.append(f"Watch: {g['streaming_url']}")
    desc.append(f"Full schedule: {SITE}?player={g['player'].replace(' ', '+')}+-+{g['school'].replace(' ', '+')}&range=all")

    opponent_key = re.sub(r"[^a-z0-9]+", "", (g.get("opponent") or "tbd").lower())
    uid = f"{player_slug(g['player'])}-{g['date_iso']}-{opponent_key}@mnselectboys"

    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{FIXED_DTSTAMP}"]
    if g.get("start_utc"):
        start = datetime.strptime(g["start_utc"], "%Y-%m-%dT%H:%M:%SZ")
        lines += [f"DTSTART:{start:%Y%m%dT%H%M%SZ}", f"DTEND:{start + MATCH_LENGTH:%Y%m%dT%H%M%SZ}"]
    else:
        day = date.fromisoformat(g["date_iso"])
        lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}"]
    lines += [f"SUMMARY:{_escape(summary)}", f"DESCRIPTION:{_escape(chr(10).join(desc))}"]
    if g.get("location"):
        lines.append(f"LOCATION:{_escape(g['location'])}")
    if (g.get("status") or "").lower() in ("canceled", "cancelled", "ppd", "postponed"):
        lines.append("STATUS:CANCELLED")
    lines.append("END:VEVENT")
    return lines


def _calendar(name, games):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MN Select Alumni//Volleyball Schedules//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        # Hints for how often apps should re-check (Apple honours these;
        # Google ignores them and refreshes on its own schedule).
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for g in games:
        lines += _event(g)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def _current_season(games):
    """Drop players whose season is over (same rule as the page), so a feed
    never shows last year's games as if they were current."""
    today = date.today().isoformat()
    last = {}
    for g in games:
        if g.get("date_iso"):
            last[g["player"]] = max(last.get(g["player"], ""), g["date_iso"])
    return [g for g in games if g.get("date_iso") and last.get(g["player"], "") >= today]


def write_calendars(all_games, players):
    """players: [{"player", "school"}, ...]. Returns {player: relative path}."""
    os.makedirs(CAL_DIR, exist_ok=True)
    games = sorted(_current_season(all_games), key=lambda g: (g["date_iso"], g.get("start_utc") or ""))
    paths, wanted = {}, {"all.ics"}

    for p in players:
        name = f"{player_slug(p['player'])}.ics"
        wanted.add(name)
        mine = [g for g in games if g["player"] == p["player"]]
        _write(os.path.join(CAL_DIR, name), _calendar(f"{p['player']} - {p['school']} volleyball", mine))
        paths[p["player"]] = f"{CAL_DIR}/{name}"

    _write(os.path.join(CAL_DIR, "all.ics"), _calendar("MN Select alumni volleyball", games))

    for stale in set(os.listdir(CAL_DIR)) - wanted:  # a player was removed
        if stale.endswith(".ics"):
            os.remove(os.path.join(CAL_DIR, stale))
    return paths


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
