"""
rss_parser.py
Last updated: 2026-08-05

Parses a PrestoSports RSS composite feed (e.g.
https://YOURSITE.com/sports/mvball/composite?print=rss) into structured
game records. This is a genuinely different, cleaner data source than
scraping the HTML schedule table - PrestoSports built custom RSS
extensions (the ps: namespace) specifically for this kind of syndication,
giving us clean <ps:opponent> and <ps:score> fields directly.

Confirmed against real data from Olivet Nazarene's feed.

FIELD NOTES:
- <ps:opponent> contains an optional "vs. "/"at " prefix (home/away),
  the opponent name, and an optional " @ location" suffix. Sometimes the
  location part is actually a tournament name instead of a real place
  (e.g. "vs. Morningside @ Missouri Valley Tournament") - same ambiguity
  we've already seen on the HTML pages, nothing new to solve here.
- <ps:score> is empty for games that haven't been played yet, otherwise
  already formatted as "W, 3-1" / "L, 0-3" - same shape we use elsewhere.
- Date and LOCAL time come from the human-readable <description> field
  (e.g. "Men's Volleyball on Jan 22, 2026 at 2:00 PM: ..."), not from
  <dc:date> - that field is in UTC, and converting it back to local time
  correctly would mean re-deriving DST rules for no real benefit when
  the description already states it in local terms directly.
- Some games have no time at all in the description (older scrimmages) -
  time is just left null in that case.
"""

import re
import xml.etree.ElementTree as ET

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "ps": "http://www.prestosports.com/rss/schedule",
}

DESC_RE = re.compile(
    r"on ([A-Za-z]+ \d{1,2}, \d{4})(?: at (\d{1,2}:\d{2} [AP]M))?:"
)
RESULT_RE = re.compile(r"^([WL]),\s*(\d+)-(\d+)$")


def _parse_opponent(raw):
    if raw is None:
        return "neutral", None, None
    text = raw.strip()
    home_away = "neutral"
    if text.lower().startswith("vs. "):
        home_away = "home"
        text = text[4:]
    elif text.lower().startswith("at "):
        home_away = "away"
        text = text[3:]

    if " @ " in text:
        opponent, location = text.split(" @ ", 1)
    else:
        opponent, location = text, None

    return home_away, opponent.strip(), (location.strip() if location else None)


def parse_rss_schedule(xml_text):
    root = ET.fromstring(xml_text)
    games = []

    for item in root.findall(".//item"):
        description_el = item.find("description")
        description = description_el.text if description_el is not None else ""

        m = DESC_RE.search(description or "")
        date_display, time_display = None, None
        if m:
            date_display = m.group(1)
            time_display = m.group(2)

        opponent_el = item.find("ps:opponent", NS)
        home_away, opponent, location = _parse_opponent(
            opponent_el.text if opponent_el is not None else None
        )

        score_el = item.find("ps:score", NS)
        score_text = (score_el.text or "").strip() if score_el is not None else ""
        result, sets = None, None
        sm = RESULT_RE.match(score_text)
        if sm:
            result = sm.group(1)
            sets = f"{sm.group(2)}-{sm.group(3)}"

        games.append({
            "date": date_display,
            "time": time_display,
            "home_away": home_away,
            "opponent": opponent,
            "location": location,
            "result": result,
            "sets": sets,
            "status": "Final" if result else None,
            "video_url": None,
        })

    return games


if __name__ == "__main__":
    import json
    import sys

    fixture_path = sys.argv[1] if len(sys.argv) > 1 else "fixture_onu_rss.xml"
    with open(fixture_path, encoding="utf-8") as f:
        xml_text = f.read()

    games = parse_rss_schedule(xml_text)
    print(json.dumps(games, indent=2))
    print(f"\n{len(games)} games parsed", file=sys.stderr)
