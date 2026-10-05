#!/bin/zsh
set -euo pipefail
APP="$HOME/Applications/PS_Scanner_Final"
if [[ ! -x "$APP/.venv/bin/python" ]]; then
  echo "PS Scanner runtime is not installed at $APP" >&2
  exit 1
fi
cd "$APP"
"$APP/.venv/bin/python" "$APP/tools/configure_groww.py"
LABEL="com.psscanner.final"
launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true
echo
echo "PS Scanner service restarted. Open http://127.0.0.1:8765"
