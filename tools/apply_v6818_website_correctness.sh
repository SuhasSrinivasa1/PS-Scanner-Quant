#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${PS_SCANNER_APP:-$HOME/Applications/PS_Scanner_Final}"
URL="${PS_SCANNER_URL:-http://127.0.0.1:8765}"

echo "PS Scanner Quant v6.8.18 complete website correctness repair"
echo "Source: $ROOT"
echo "Target: $APP"

for f in "$ROOT/psscanner_quant/constants.py" "$ROOT/static/index.html" "$ROOT/install.sh"; do
  [[ -f "$f" ]] || { echo "ERROR: missing release file: $f" >&2; exit 2; }
done

VERSION="$(PYTHONPATH="$ROOT" python3 - <<'PY'
from psscanner_quant.constants import VERSION
print(VERSION)
PY
)"
[[ "$VERSION" == "6.8.18" ]] || { echo "ERROR: expected v6.8.18 source, found $VERSION" >&2; exit 3; }

echo "Validating website source contract..."
grep -q 'id="executionPill"' "$ROOT/static/index.html"
grep -q 'id="opsExecution"' "$ROOT/static/index.html"
grep -q 'function workerUi' "$ROOT/static/index.html"
grep -q 'function growwUi' "$ROOT/static/index.html"
grep -q 'function ipUi' "$ROOT/static/index.html"
grep -q 'function executionUi' "$ROOT/static/index.html"
grep -q "UNKNOWN_NOT_PROBED" "$ROOT/static/index.html"
grep -q "v.alive===false" "$ROOT/static/index.html"

echo "Installing through the production in-place upgrader..."
zsh "$ROOT/install.sh"

echo "Waiting for localhost..."
ok=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 "$URL/api/health" >/tmp/psscanner-v6818-health.json 2>/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
[[ "$ok" == "1" ]] || { echo "ERROR: $URL/api/health did not become ready." >&2; exit 4; }

echo "Validating served website..."
curl -fsS --max-time 5 "$URL/" >/tmp/psscanner-v6818-index.html
grep -q 'v6.8.18' /tmp/psscanner-v6818-index.html
grep -q 'id="executionPill"' /tmp/psscanner-v6818-index.html
grep -q 'function executionUi' /tmp/psscanner-v6818-index.html

"$APP/.venv/bin/python" - <<'PY'
import json, urllib.request

url="http://127.0.0.1:8765"
with urllib.request.urlopen(url+"/api/health",timeout=5) as r:
    h=json.load(r)

print("version:",h.get("version"))
print("build:",h.get("build_commit"))
print("engine_alive:",h.get("engine_alive"))
print("groww:",(h.get("groww") or {}).get("status"))
print("static_ip:",(h.get("static_ip") or {}).get("state"))
print("execution_ready:",(h.get("execution") or {}).get("ready"))
print("execution_blockers:",(h.get("execution") or {}).get("blockers"))

if h.get("version")!="6.8.18":
    raise SystemExit("wrong installed version")

for name in ("daily_history","weekly","circuit"):
    w=(h.get("workers") or {}).get(name,{})
    print("\n==",name,"==")
    for k in ("state","current_stage","processed","remaining","current_item",
              "elapsed_seconds","runtime_over_threshold","last_progress_at",
              "progress_age_seconds","stall_grace_seconds","hung","last_error"):
        print(f"{k}: {w.get(k)}")
PY

echo
echo "Running production validator..."
"$APP/.venv/bin/python" "$APP/tools/post_install_validate.py"

echo
echo "v6.8.18 website correctness repair verified."
