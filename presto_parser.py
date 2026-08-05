"""
presto_parser.py
Last updated: 2026-07-11 (fixed # marker stripping conflicting with rank prefixes like #13)

Parses a PrestoSports schedule page (used by Olivet Nazarene and Orange Coast)
into structured game records. Unlike Sidearm, PrestoSports renders the
schedule as a genuine HTML <table>, so we parse actual <tr>/<td> structure
via BeautifulSoup rather than flattened text - much less ambiguous.

KEY STRUCTURE (confirmed from real Orange Coast + Olivet Nazarene pages):
- The table header row names the columns. Seen so far: Date, Opponent,
  Result, Status, Links (Orange Coast) and Date, Opponent, Notes, Result,
  Status, Links (Olivet Nazarene - has an extra venue/tournament column).
  We read the header to map columns dynamically rather than assuming
  fixed positions, so this should handle minor column differences.
- Month header rows ("January", "February", ...) span the row with mostly
  empty cells - skipped.
- A "continuation" row (set-by-set score detail, e.g. "Nonconference:
  25-22, 22-25, 25-19, 25-21") has blank Date/Result/Status - skipped,
  since we already get the overall set score from the Result column.
- The Opponent cell contains "VS" or "AT" (home/away), the team name
  (sometimes with a trailing "*" for conference or "%" for postseason),
  and sometimes a leading rank/logo alt text.
- The "Video" link (when present) is our best stand-in for a streaming
  link on these pages - PrestoSports schools don't show a separate
  network/TV field the way some Sidearm schools do.

ASSUMPTION NOT YET VERIFIED: neither real sample we tested against had any
upcoming (not-yet-played) games, since both pages currently show a
completed season. An upcoming game's Status column is expected to show a
time (e.g. "7:00 PM") or "TBA" instead of "Final", with Result blank -
worth double-checking once real upcoming games are visible on the page.
"""

import re

from bs4 import BeautifulSoup

MONTH_NAMES = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}
RESULT_RE = re.compile(r"^([WL]),\s*(\d+)-(\d+)$")
RANK_PREFIX_RE = re.compile(r"^(No\.\s*\d+|#\d+|#RV)\s*")
MARKER_RE = re.compile(r"\s*[*%]+\s*|\s*#(?!\d)\s*")


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _parse_opponent_cell(cell_text):
    """
    Returns (home_away, opponent_name). Cell text looks like:
    'VS Santa Monica', 'AT Fullerton', 'VS Judson (IL) *', 'VS Judson (IL) %'
    """
    text = _clean(cell_text)
    home_away = "neutral"
    if text.upper().startswith("VS "):
        home_away = "home"
        text = text[3:]
    elif text.upper().startswith("AT "):
        home_away = "away"
        text = text[3:]
    text = MARKER_RE.sub(" ", text).strip()
    text = RANK_PREFIX_RE.sub("", text)
    return home_away, text.strip()


def _is_month_header_row(cells):
    if not cells:
        return False
    first = _clean(cells[0].get_text())
    return first.lower() in MONTH_NAMES and all(
        _clean(c.get_text()) == "" for c in cells[1:]
    )


def _is_continuation_row(cells, col_index):
    """A set-score detail row: Date/Result/Status blank, Opponent has text."""
    date_idx = col_index.get("date")
    result_idx = col_index.get("result")
    status_idx = col_index.get("status")
    opponent_idx = col_index.get("opponent")

    def blank(idx):
        return idx is None or idx >= len(cells) or _clean(cells[idx].get_text()) == ""

    has_opponent_text = (
        opponent_idx is not None
        and opponent_idx < len(cells)
        and _clean(cells[opponent_idx].get_text()) != ""
    )
    return blank(date_idx) and blank(result_idx) and blank(status_idx) and has_opponent_text


def parse_presto_schedule(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Map column names -> index from the header row
    header_cells = rows[0].find_all(["th", "td"])
    col_index = {}
    for i, cell in enumerate(header_cells):
        name = _clean(cell.get_text()).lower()
        if name:
            col_index[name] = i

    games = []
    last_date = None
    current_month = None
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        if _is_month_header_row(cells):
            current_month = _clean(cells[0].get_text()).title()
            continue
        if _is_continuation_row(cells, col_index):
            continue

        def get(name):
            idx = col_index.get(name)
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx]

        date_cell = get("date")
        date_text = _clean(date_cell.get_text()) if date_cell else ""
        if date_text:
            # date_text looks like "Sat. 24" - combine with the current month
            day_num_match = re.search(r"(\d+)", date_text)
            day_num = day_num_match.group(1) if day_num_match else date_text
            last_date = f"{current_month} {day_num}" if current_month else date_text

        opponent_cell = get("opponent")
        opponent_text = opponent_cell.get_text() if opponent_cell else ""
        home_away, opponent = _parse_opponent_cell(opponent_text)
        if not opponent:
            continue  # not a real game row

        notes_cell = get("notes")
        location = _clean(notes_cell.get_text()) if notes_cell else None

        result_cell = get("result")
        result_text = _clean(result_cell.get_text()) if result_cell else ""
        result, sets = None, None
        m = RESULT_RE.match(result_text)
        if m:
            result = m.group(1)
            sets = f"{m.group(2)}-{m.group(3)}"

        status_cell = get("status")
        status = _clean(status_cell.get_text()) if status_cell else None

        links_cell = get("links")
        video_url = None
        if links_cell:
            for a in links_cell.find_all("a"):
                if _clean(a.get_text()).lower() == "video":
                    video_url = a.get("href")
                    break

        games.append({
            "date": last_date,
            "home_away": home_away,
            "opponent": opponent,
            "location": location,
            "result": result,
            "sets": sets,
            "status": status,
            "video_url": video_url,
        })

    return games


if __name__ == "__main__":
    import json
    import sys

    fixture_path = sys.argv[1] if len(sys.argv) > 1 else "fixture_occ.html"
    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()

    games = parse_presto_schedule(html)
    print(json.dumps(games, indent=2))
    print(f"\n{len(games)} games parsed", file=sys.stderr)
