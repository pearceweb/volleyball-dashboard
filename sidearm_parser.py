"""
sidearm_parser.py
Last updated: 2026-07-11 (handles upcoming games with no Hide/Show marker)

Parses the visible text of a Sidearm Sports schedule page into structured
game records.

KEY INSIGHTS (learned from real debug output across multiple schools):
- Sidearm renders each game's info TWICE in the extracted text (a duplicate
  "card" and "table row" view), and splits the W/L result and the score onto
  two separate lines ("W," then "3-0"). The one reliable, non-duplicated
  delimiter between games is the line "Hide/Show Additional Information For",
  which appears exactly once per real game. We split on that instead of on
  the (duplicated) date line.
- That marker itself renders two different ways depending on the school:
  combined on one line ("...For X - Date") or split across three lines
  (marker / "X -" / "Date"). We detect which case we're in per-block.
- Opponent detection: when a standalone "vs"/"at" line is present, the
  opponent is the very next line - this is the most reliable signal and
  sidesteps venue-name traps (e.g. a school's own gym name showing up
  right before the result with no comma to distinguish it). When no
  vs/at marker exists, we fall back to the nearest substantive line
  before the result, skipping known noise/label lines and locations.
- Time can appear as "6 p.m." or "9:00 PM" depending on the school.
"""

import re

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_RE = re.compile(rf"^({MONTHS})\s+(\d{{1,2}})\s*\((\w{{3}})\)", re.IGNORECASE)
TIME_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[ap]\.m\.)", re.IGNORECASE)
TIME_RE2 = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)")
RESULT_RE = re.compile(r"^([WL]),\s*(\d+)-(\d+)$")
RESULT_LABEL_RE = re.compile(r"^([WL]),?$")
SCORE_ONLY_RE = re.compile(r"^(\d+)-(\d+)$")
TV_RE = re.compile(r"^TV:\s*(.+)$", re.IGNORECASE)
RANK_PREFIX_RE = re.compile(r"^(No\.\s*\d+|#\d+|#RV|\(\d+\))\s+")
CONFERENCE_TAG_RE = re.compile(r"^[A-Za-z0-9]+\s*\*$")
ALL_CAPS_LABEL_RE = re.compile(r"^[A-Z][A-Z\s]{2,}$")
PHOTO_CREDIT_RE = re.compile(r"\bphoto\b|\binc\.?$", re.IGNORECASE)
HIDE_SHOW_MARKER = "Hide/Show Additional Information For"
NOISE_LINES = {
    "/", "final", "recap", "box score", "scheduled games",
    "history", "game program",
}
STATUS_WORDS = {"canceled", "cancelled", "ppd", "postponed"}


def _clean_lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _merge_split_results(lines):
    """Merge a 'W,' / 'L,' line with a following bare '3-0' score line."""
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if RESULT_LABEL_RE.match(line) and i + 1 < len(lines) and SCORE_ONLY_RE.match(lines[i + 1]):
            label = line.rstrip(",")
            merged.append(f"{label}, {lines[i + 1]}")
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged


def _date_time_signature(line):
    """Returns (date, time) if this line starts a date, else None."""
    m = DATE_RE.match(line)
    if not m:
        return None
    date_part = f"{m.group(1)} {m.group(2)}"
    t = TIME_RE.search(line) or TIME_RE2.search(line)
    time_part = t.group(1) if t else None
    return (date_part, time_part)


def _split_into_blocks(lines):
    """
    Split into per-game chunks. Two delimiters are used, since real pages
    use different formats depending on whether the game has been played:

    1. 'Hide/Show Additional Information For' - appears once per real game
       AFTER it's been played (once a box score/recap exists). Renders
       either combined on one line or split across three.
    2. Date-signature repeat - for games NOT YET PLAYED, there's no
       Hide/Show marker at all (confirmed on North Park's 2027 schedule,
       which is all upcoming games). Sidearm still renders each game
       TWICE (duplicate mobile/desktop views), so the date+time line
       appears twice in a row for the same game. We track the date+time
       signature of the block currently being built; a repeat of that
       exact signature means "still the same game" (fold in), while a
       DIFFERENT signature means a genuinely new game (split).
    """
    blocks = []
    current = []
    current_sig = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith(HIDE_SHOW_MARKER):
            if current:
                blocks.append(current)
            current = []
            current_sig = None
            if line.strip() == HIDE_SHOW_MARKER:
                i += 1
                if i < n:
                    i += 1
                if i < n:
                    i += 1
            else:
                i += 1
            continue

        sig = _date_time_signature(line)
        if sig is not None:
            if current_sig is None:
                current_sig = sig
            elif sig[0] != current_sig[0]:
                # different date - genuinely a new game
                if current:
                    blocks.append(current)
                current = []
                current_sig = sig
            elif sig[1] and current_sig[1] and sig[1] != current_sig[1]:
                # same date, but both have a time and they differ - a
                # same-day doubleheader, so this is a new game too
                if current:
                    blocks.append(current)
                current = []
                current_sig = sig
            else:
                # same date, and either the times match or one copy is
                # just missing its time (the duplicate mobile/desktop
                # render often omits it) - still the same game. Keep
                # whichever signature has a concrete time value.
                if not current_sig[1] and sig[1]:
                    current_sig = sig

        current.append(line)
        i += 1
    if current:
        # leftover trailing content with no Hide/Show marker (rare) - keep if
        # it actually contains a date, otherwise discard as trailing noise
        if any(DATE_RE.match(ln) for ln in current):
            blocks.append(current)
    return blocks


def _parse_block(block):
    game = {
        "date": None,
        "time": None,
        "tv": None,
        "home_away": "neutral",
        "opponent": None,
        "location": None,
        "result": None,
        "sets": None,
        "status": None,
    }

    # date/time: first matching line in the block (ignore any repeat)
    for line in block:
        m = DATE_RE.match(line)
        if m:
            game["date"] = f"{m.group(1)} {m.group(2)}"
            t = TIME_RE.search(line) or TIME_RE2.search(line)
            if t:
                game["time"] = t.group(1)
            break

    # if time wasn't on the date line itself, it's often its own line right after
    if game["time"] is None:
        for line in block:
            t = TIME_RE.search(line) or TIME_RE2.search(line)
            if t and not DATE_RE.match(line):
                game["time"] = t.group(1)
                break

    # result: first merged "W, 3-0" / "L, 2-3" style line
    result_idx = None
    for idx, line in enumerate(block):
        m = RESULT_RE.match(line)
        if m:
            w_l, s1, s2 = m.groups()
            game["result"] = "W" if w_l == "W" else "L"
            game["sets"] = f"{s1}-{s2}"
            result_idx = idx
            break
        if line.lower() in STATUS_WORDS:
            game["status"] = line
            result_idx = idx
            break

    def _is_noise(candidate):
        low = candidate.lower()
        return (
            low in NOISE_LINES
            or DATE_RE.match(candidate)
            or CONFERENCE_TAG_RE.match(candidate)
            or candidate.lower() in ("vs", "at")
            or TV_RE.match(candidate)
            or ALL_CAPS_LABEL_RE.match(candidate)
            or TIME_RE.search(candidate)
            or TIME_RE2.search(candidate)
        )

    opponent_idx = None

    # Strategy 1 (most reliable): opponent is the line right after a
    # standalone "vs"/"at" marker, if one exists in this block.
    for idx, line in enumerate(block):
        if line.lower() in ("vs", "at"):
            game["home_away"] = "home" if line.lower() == "vs" else "away"
            if idx + 1 < len(block):
                candidate = block[idx + 1]
                game["opponent"] = RANK_PREFIX_RE.sub("", candidate).strip()
                opponent_idx = idx + 1
            break

    # Strategy 2 (fallback): nearest substantive line immediately before
    # the result, skipping known noise/labels and location lines.
    if game["opponent"] is None and result_idx is not None:
        j = result_idx - 1
        while j >= 0:
            candidate = block[j]
            if _is_noise(candidate) or "," in candidate:
                j -= 1
                continue
            game["opponent"] = RANK_PREFIX_RE.sub("", candidate).strip()
            opponent_idx = j
            break

    # location: first comma-containing line anywhere in the block, excluding
    # the date line, the result line, and whichever line we used as opponent
    # (some opponent names legitimately contain a comma, e.g. "University of
    # California, Santa Cruz")
    for idx, line in enumerate(block):
        if idx == opponent_idx:
            continue
        if "," in line and not DATE_RE.match(line) and not RESULT_RE.match(line) and not PHOTO_CREDIT_RE.search(line):
            game["location"] = line
            break

    # TV/streaming
    for line in block:
        m = TV_RE.match(line)
        if m:
            game["tv"] = m.group(1).strip()
            break

    return game


def parse_sidearm_schedule(text):
    lines = _clean_lines(text)
    lines = _merge_split_results(lines)
    blocks = _split_into_blocks(lines)
    games = [_parse_block(b) for b in blocks]

    # Forward-fill missing dates (tournament days sometimes only show the
    # date once, on the first game of that day)
    last_date, last_time = None, None
    for g in games:
        if g["date"] is None:
            g["date"] = last_date
            g["time"] = g["time"] or last_time
        else:
            last_date, last_time = g["date"], g["time"]

    return games


if __name__ == "__main__":
    import json
    import sys

    fixture_path = sys.argv[1] if len(sys.argv) > 1 else "fixture_uwsp_real.txt"
    with open(fixture_path, encoding="utf-8") as f:
        text = f.read()

    games = parse_sidearm_schedule(text)
    print(json.dumps(games, indent=2))
    print(f"\n{len(games)} games parsed", file=sys.stderr)
