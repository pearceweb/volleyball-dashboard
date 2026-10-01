#!/bin/bash
# setup_mac_mini.sh
#
# Sets up the twice-daily PrestoSports job (scripts/local_presto_update.sh)
# on a Mac - built for the always-on Mac mini. Safe to re-run.
#
# Run on the Mac mini, in Terminal:
#   bash <(curl -fsSL https://raw.githubusercontent.com/pearceweb/volleyball-dashboard/main/scripts/setup_mac_mini.sh)
#
# It will:
#   1. Install Homebrew and the GitHub CLI (gh) if missing
#   2. Sign in to GitHub (opens your browser) if not already signed in
#   3. Make a private Python environment with the scraper's packages
#   4. Clone the repo into ~/Library/Application Support/volleyball-dashboard-updater/
#   5. Install the launchd job (9:00 AM and 6:00 PM daily) and run it once

set -euo pipefail

REPO_URL="https://github.com/pearceweb/volleyball-dashboard.git"
UPDATER_DIR="$HOME/Library/Application Support/volleyball-dashboard-updater"
LABEL="com.pearceweb.volleyball-presto"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/volleyball-presto-update.log"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

step "1/5  Homebrew and GitHub CLI"
if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ] && [ ! -x /usr/local/bin/brew ]; then
  echo "Installing Homebrew (it will ask for this Mac's password)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$( (/opt/homebrew/bin/brew shellenv || /usr/local/bin/brew shellenv) 2>/dev/null)"
command -v gh >/dev/null 2>&1 || brew install gh
command -v python3 >/dev/null 2>&1 || brew install python
echo "gh: $(gh --version | head -1)   python: $(python3 --version)"

step "2/5  GitHub sign-in"
if ! gh auth status >/dev/null 2>&1; then
  echo "Choose: GitHub.com -> HTTPS -> Yes (authenticate Git) -> Login with a web browser"
  gh auth login
fi
gh auth setup-git
gh auth status 2>&1 | grep -E "Logged in" || { echo "GitHub sign-in failed"; exit 1; }

step "3/5  Python environment"
mkdir -p "$UPDATER_DIR"
[ -x "$UPDATER_DIR/venv/bin/python3" ] || python3 -m venv "$UPDATER_DIR/venv"
"$UPDATER_DIR/venv/bin/pip" install -q --upgrade pip requests beautifulsoup4
echo "Installed requests + beautifulsoup4 in $UPDATER_DIR/venv"

step "4/5  Repo copy"
if [ -d "$UPDATER_DIR/repo/.git" ]; then
  git -C "$UPDATER_DIR/repo" fetch -q origin && git -C "$UPDATER_DIR/repo" reset -q --hard origin/main
else
  git clone -q "$REPO_URL" "$UPDATER_DIR/repo"
fi
# Name on this machine's automatic commits
git -C "$UPDATER_DIR/repo" config user.name "Volleyball Mac mini job"
git -C "$UPDATER_DIR/repo" config user.email "pearceweb@users.noreply.github.com"
git -C "$UPDATER_DIR/repo" log --oneline -1

step "5/5  Daily job"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$UPDATER_DIR/repo/scripts/local_presto_update.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$LOG</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Running the job once to test (about a minute)..."
: > "$LOG"
launchctl kickstart "gui/$(id -u)/$LABEL"
for _ in $(seq 1 60); do
  sleep 3
  launchctl print "gui/$(id -u)/$LABEL" | grep -q "state = running" || break
done
echo "----- job log -----"
cat "$LOG"
echo "-------------------"
code=$(launchctl print "gui/$(id -u)/$LABEL" | awk '/last exit code/ {print $NF}')
if [ "$code" = "0" ]; then
  printf '\n\033[1;32mDone - the Mac mini will now run the job at 9 AM and 6 PM daily.\033[0m\n'
else
  printf '\n\033[1;31mThe test run exited with code %s - send the log above to Claude.\033[0m\n' "$code"
fi
echo "Reminder: System Settings -> Energy -> turn ON \"Prevent automatic sleeping when the display is off\"."
