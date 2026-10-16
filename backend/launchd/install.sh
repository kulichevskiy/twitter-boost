#!/usr/bin/env bash
# Installs the API and worker as launchd agents for the current user.
# Usage: backend/launchd/install.sh        (re-run to update after edits)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
backend="$(cd "$here/.." && pwd)"
uv="$(command -v uv || echo "$HOME/.local/bin/uv")"
mkdir -p "$backend/data" "$HOME/Library/LaunchAgents"
for name in crm-api crm-worker; do
  label="com.twitter-boost.$name"
  target="$HOME/Library/LaunchAgents/$label.plist"
  sed -e "s|__UV__|$uv|g" -e "s|__BACKEND_DIR__|$backend|g" -e "s|__HOME__|$HOME|g" "$here/$label.plist" > "$target"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$target"
  echo "loaded $label"
done
echo "logs: $backend/data/api.log, $backend/data/worker.log"
