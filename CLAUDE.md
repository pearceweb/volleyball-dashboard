# MN Select Alumni — College Volleyball Schedules

Live site: https://mnselectboys.tuckerpearcecreative.com (GitHub Pages for
`pearceweb/volleyball-dashboard`; old `pearceweb.github.io/volleyball-dashboard`
links redirect). Shows the men's college volleyball schedules of Tucker
Pearce's former club players (MN Select 18-1).

**All players are college freshmen in 2026-27** — spring 2027 is everyone's
first college season. Any 2025-26 data for a school predates the player and
must never be presented as theirs (the page hides finished seasons).

The project is worked on from two Macs (laptop and Mac mini). GitHub is the
source of truth. **Tucker only works on this through Claude, never in the
terminal himself — so syncing is Claude's job:** at the start of every
session run `git pull --rebase --autostash` before reading or changing
anything (the Mac mini job and GitHub Actions push data updates throughout
the day), and commit + push finished work before the session ends.
Commits go straight to `main` (no pull-request workflow).

## How data flows

1. **Fetch**
   - `fetch_sidearm_schedules.py` + `sidearm_parser.py` — Sidearm Sports
     schools. Runs on GitHub Actions every 6h (`.github/workflows/update-schedule.yml`).
   - `fetch_presto_schedules.py` + `presto_parser.py` — PrestoSports schools
     (Olivet Nazarene, Orange Coast). PrestoSports blocks GitHub's servers, so
     this runs on a Mac via launchd (see "Mac job" below).
   - `fetch_rss_schedules.py` / `rss_parser.py` — older RSS approach, unused
     (lower-quality data: no watch links, poor home/away).
2. **Build** — `build_unified_schedule.py` merges both into
   `unified_schedule.json`, writes `players.json` (every configured player,
   even with no games) and calls `build_calendars.py` to write subscribable
   feeds `calendars/<player-slug>.ics` + `calendars/all.ics`.
3. **Health check** — `check_health.py` compares against the previous run;
   the workflow emails on problems (once when a problem starts, not every run).
4. **Page** — `index.html` (single file, no build step) loads
   `unified_schedule.json` + `players.json`.

## Behaviours worth knowing

- **Season auto-advance**: both fetchers check the next season's page each
  run and switch once it has real games (Sidearm: `/schedule/<year+1>`;
  Presto: `/<yyyy-yy>/schedule` returns 404 until posted). A switch emails
  Tucker. Config URLs don't need bumping by hand.
- **Outage safety**: if a school's fetch errors, or suddenly returns 0 games
  when it had some, the last good games are kept and an error is recorded.
- **Time zones**: schools list times in their own zone unless labelled
  ("Noon ET", Presto "7:00 PM CST"). The build stores `tz` + exact
  `start_utc`; the page shows the visitor's zone plus "local" time at the
  game; calendars use UTC.
- **Parser gotchas (Sidearm)**: same-day doubleheaders with times on their own
  line, matches between two other teams at a shared event ("Hunter vs Kean" —
  skipped), venue names next to opponents, and page-footer text after the last
  game (parsing stops at "Score By Period"/"Related Headlines"). After any
  parser change, diff the output for every school before committing.
- **Presto data cleanup** (in the build): "Hastings @ Sioux City, Iowa" →
  neutral site in Sioux City; times live in the status column; relative watch
  links are made absolute.
- **Hand-added games**: `manual_games.json` holds games the school sites
  don't list (fall scrimmages). The build merges them in every run, so the
  jobs never wipe them, and skips one once the school's own schedule shows a
  game for that school on that day. Fields: school, date (YYYY-MM-DD), time
  ("7:00 PM", school's zone), home_away, opponent, location, watch_url.
- **MN Select matchups**: games where the opponent is another player's school
  are tagged (`matchup_with`) and shown on the page.

## Adding a player / school

1. Add the entry to `SCHOOLS` in `fetch_sidearm_schedules.py` or
   `fetch_presto_schedules.py` (player, school, schedule URL).
2. In `build_unified_schedule.py`, add the school to `SCHOOL_TZ` (IANA zone),
   `SCHOOL_ALIASES` (names opponents use for it) and `SCHOOL_INSTAGRAM`
   (team Instagram handle, linked at the top of the player's page).
3. Run the fetch + build locally, check the page, commit, push.

## Mac job (PrestoSports)

- `scripts/local_presto_update.sh`, run by launchd job
  `com.pearceweb.volleyball-presto` at 9:00 and 18:00, in its own clone at
  `~/Library/Application Support/volleyball-dashboard-updater/repo` (never the
  working folder). It resets to `origin/main`, fetches, rebuilds, pushes if
  anything changed, and asks the workflow to email notices (`notify_message`
  input) since the Gmail password lives only in GitHub secrets.
- Set up on a Mac with `scripts/setup_mac_mini.sh` (one-line command in its
  header). Log: `~/Library/Logs/volleyball-presto-update.log`.
- Only one Mac should run the job: since 2026-10-01 that's the always-on
  Mac mini (the laptop's job was removed). To stop it on a Mac:
  `launchctl bootout gui/$(id -u)/com.pearceweb.volleyball-presto` and delete
  `~/Library/LaunchAgents/com.pearceweb.volleyball-presto.plist`.

## Visit counting

GoatCounter (dashboard: https://tuckerpearcecreative.goatcounter.com; no
cookies). `index.html` reports views itself (`no_onload`): `/` for all
players, `/player/<slug>` per player (dropdown switches count too), and
clicks on elements with `data-track="name"` as events (`name/<player>`).
Add `data-track` to new buttons/links worth measuring. GoatCounter ignores
localhost; visiting the site with `#toggle-goatcounter` stops counting that
browser's own visits.

## Email alerts

GitHub repo secrets `MAIL_USERNAME`, `MAIL_PASSWORD` (a Gmail **app password**
for a Google Workspace account Tucker administers) and `NOTIFY_TO`. Manual
workflow runs have a "Send a test email" checkbox. Never put the password
anywhere else.

## Testing

- Serve locally: `python3 -m http.server 8765` in the repo, open
  `http://localhost:8765/`.
- Results/records only appear once games are played — test them with a
  throwaway copy of `unified_schedule.json` containing fake recent results,
  never by committing fake data.
- `scripts/make_share_images.py` regenerates `og-image.png` (link previews)
  and `apple-touch-icon.png`.

## Domain

`mnselectboys` is a CNAME at Porkbun → `pearceweb.github.io` (custom domain
set in repo Settings → Pages; the `CNAME` file is GitHub's). Tucker's main
site `www.tuckerpearcecreative.com` is on Pixpa; the bare domain is a Porkbun
301 forward to www (keeps path). Don't add wildcard DNS records.

## Ideas not yet built

- Game-day "Today" view with live-stats/stream links (best done just before
  the season, ~Jan 2027, when links exist to test).
- "Catch them in person" — games within driving distance of the Twin Cities.
- Player cards with Tucker's media-day photos, jersey number, roster link.
- Player stats from box scores; weekly Instagram schedule graphic.
- Declined: email sign-up notifications (calendar subscriptions cover it).
