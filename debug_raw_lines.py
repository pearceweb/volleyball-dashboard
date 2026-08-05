#!/usr/bin/env python3
"""
debug_raw_lines.py

Diagnostic tool: fetches ONE schedule page and prints the raw, line-numbered
text that BeautifulSoup extracts, so we can see exactly why games are being
mis-parsed. Prints the first ~90 lines (should cover 3-5 games).

Usage:
    python3 debug_raw_lines.py                     # defaults to UW-Stevens Point
    python3 debug_raw_lines.py <schedule-url>       # any Sidearm school
"""

import sys

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://athletics.uwsp.edu/sports/mens-volleyball/schedule/2026"
URL = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

resp = requests.get(URL, headers=HEADERS, timeout=20)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")
text = soup.get_text(separator="\n")

lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

# Find where the schedule actually starts (first "Jan" or "Scheduled Games")
start = 0
for i, ln in enumerate(lines):
    if "Scheduled Games" in ln or ln.startswith("Jan "):
        start = i
        break

for i, ln in enumerate(lines[start:start + 90]):
    print(f"{i:3d}: {ln!r}")

