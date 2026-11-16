#!/usr/bin/env bash
# Runs PROGRESS_CHECK.md in DAILY MODE (report only) and saves the report.

# make Homebrew, Docker and Claude findable when run by cron
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.npm-global/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

# go to the repo folder (where this script lives)
cd "$(dirname "$0")" || exit 1

# folder for reports
mkdir -p progress-reports
REPORT="progress-reports/$(date +%F).md"

# run Claude headless with read-only tools
claude -p "Follow PROGRESS_CHECK.md in DAILY MODE. Output only the Markdown report." \
  --allowedTools "Read,Grep,Glob,Bash(date),Bash(ls:*),Bash(git status:*),Bash(git log:*),Bash(git check-ignore:*),Bash(gh issue list:*),Bash(gh project list:*),Bash(gh run list:*),Bash(gh release list:*),Bash(docker info:*),Bash(docker build:*),Bash(docker compose:*),Bash(curl:*),Bash(dig:*)" \
  > "$REPORT" 2>&1

# pop up a Mac notification when finished
osascript -e "display notification \"Report saved: $REPORT\" with title \"Booking project check done\""
