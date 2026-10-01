#!/bin/bash
# local_presto_update.sh
#
# Runs the PrestoSports fetch (Olivet Nazarene, Orange Coast) on the Mac,
# since PrestoSports blocks GitHub Actions' servers. launchd runs it twice a
# day from ~/Library/LaunchAgents/com.pearceweb.volleyball-presto.plist; if
# the Mac is asleep at that time it runs when it wakes.
#
# It works in its own clone of the repo (REPO_DIR below), never in the
# folder you edit in, and always starts from GitHub's latest main.
#
# Log:        ~/Library/Logs/volleyball-presto-update.log
# Run now:    launchctl kickstart gui/$(id -u)/com.pearceweb.volleyball-presto
# Turn off:   launchctl bootout gui/$(id -u)/com.pearceweb.volleyball-presto
#             rm ~/Library/LaunchAgents/com.pearceweb.volleyball-presto.plist

set -uo pipefail
export PATH="/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/usr/bin:/bin"
UPDATER_DIR="$HOME/Library/Application Support/volleyball-dashboard-updater"
REPO_DIR="${REPO_DIR:-$UPDATER_DIR/repo}"
# Use the private Python environment made by scripts/setup_mac_mini.sh when
# it exists (it has requests + beautifulsoup4); otherwise the system python3.
if [ -x "$UPDATER_DIR/venv/bin/python3" ]; then
  export PATH="$UPDATER_DIR/venv/bin:$PATH"
fi
FILES="presto_games.json unified_schedule.json players.json calendars"

# Everything runs inside main(), so bash has read the whole script before
# `git reset --hard` below rewrites this file with the latest version.
main() {
  echo "=== $(date) ==="
  cd "$REPO_DIR" || { echo "Repo not found at $REPO_DIR"; exit 1; }

  git fetch -q origin && git reset -q --hard origin/main || { echo "git fetch failed"; exit 1; }
  python3 fetch_presto_schedules.py || { echo "Fetch failed"; exit 1; }

  NEW_DATA="$(mktemp)"
  cp presto_games.json "$NEW_DATA"
  for attempt in 1 2 3; do
    python3 build_unified_schedule.py > /dev/null || { echo "Build failed"; exit 1; }
    if git diff --quiet -- $FILES; then
      echo "No changes."
      break
    fi
    git add $FILES
    git commit -q -m "Auto-update PrestoSports schedules (daily Mac job)"
    if git push -q origin main; then
      echo "Pushed changes."
      break
    fi
    # GitHub's own 6-hourly job pushed in between - start again from its
    # commit, keeping the Presto data we just fetched.
    echo "Push rejected (attempt $attempt), retrying on top of latest main"
    git fetch -q origin && git reset -q --hard origin/main
    cp "$NEW_DATA" presto_games.json
  done
  rm -f "$NEW_DATA"

  # The Gmail password lives only in GitHub's secrets, so ask the workflow to
  # send the email for us.
  if [ -s presto_season_updates.txt ]; then
    echo "New season found - requesting email"
    gh workflow run update-schedule.yml --repo pearceweb/volleyball-dashboard \
      -f notify_subject="new season schedule posted" \
      -f notify_message="$(cat presto_season_updates.txt)"
  fi
  if [ -s presto_alerts.txt ]; then
    echo "New fetch problem - requesting email"
    gh workflow run update-schedule.yml --repo pearceweb/volleyball-dashboard \
      -f notify_subject="schedule check found issues" \
      -f notify_message="$(cat presto_alerts.txt) (Last good games are being kept.)"
  fi
}

main "$@"
exit
