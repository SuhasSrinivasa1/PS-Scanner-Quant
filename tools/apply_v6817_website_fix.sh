#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${PS_SCANNER_APP:-$HOME/Applications/PS_Scanner_Final}"
URL="${PS_SCANNER_URL:-http://127.0.0.1:8765}"

echo "PS Scanner Quant v6.8.17 website/runtime repair"
echo "Source: $ROOT"
echo "Target: $APP"

if [[ ! -f "$ROOT/psscanner_quant/constants.py" || ! -f "$ROOT/install.sh" ]]; then
  echo "ERROR: run this script from the extracted v6.8.17 release." >&2
  exit 2
fi

VERSION="$(PYTHONPATH="$ROOT" python3 - <<'PY'
from psscanner_quant.constants import VERSION
print(VERSION)
PY
)"
if [[ "$VERSION" != "6.8.17" ]]; then
  echo "ERROR: expected v6.8.17 source, found $VERSION" >&2
  exit 3
fi

echo "Installing through the production in-place upgrader..."
zsh "$ROOT/install.sh"

echo "Waiting for localhost health..."
ok=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 "$URL/api/health" >/tmp/psscanner-health.json 2>/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "ERROR: $URL/api/health did not become ready." >&2
  exit 4
fi

"$APP/.venv/bin/python" - <<'PY'
import json, urllib.request
url="http://127.0.0.1:8765"
with urllib.request.urlopen(url+"/api/health",timeout=5) as r:
    h=json.load(r)
print("version:",h.get("version"))
print("build:",h.get("build_commit"))
for name in ("daily_history","weekly","circuit"):
    w=(h.get("workers") or {}).get(name,{})
    print("\n==",name,"==")
    for k in ("state","current_stage","processed","remaining","current_item",
              "elapsed_seconds","runtime_over_threshold","last_progress_at",
              "progress_age_seconds","stall_grace_seconds","hung","last_error"):
        print(f"{k}: {w.get(k)}")
if h.get("version")!="6.8.17":
    raise SystemExit("wrong installed version")
PY

echo
echo "Running production validator..."
"$APP/.venv/bin/python" "$APP/tools/post_install_validate.py"
echo "v6.8.17 website/runtime repair verified."
