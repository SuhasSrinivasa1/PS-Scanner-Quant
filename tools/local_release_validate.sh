#!/usr/bin/env bash
set -euo pipefail

VERSION="6.8.3"
LINUX_PLATFORM="${LINUX_PLATFORM:-linux/amd64}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRANCH="$(git -C "$REPO_ROOT" branch --show-current)"
HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
DIST_DIR="$REPO_ROOT/dist"
TMP_ROOT="$(mktemp -d "$REPO_ROOT/.psscanner-v683.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail(){ echo "FAIL: $*" >&2; exit 1; }

echo "PS Scanner Quant v$VERSION standalone release validation"
echo "Repository: $REPO_ROOT"
echo "Branch:     $BRANCH"
echo "HEAD:       $HEAD_SHA"

if [[ "$BRANCH" != "main" && "$BRANCH" != release/* && "${ALLOW_ANY_REF:-0}" != "1" ]]; then
  fail "expected main or release/* (set ALLOW_ANY_REF=1 only for deliberate ref validation)"
fi

git -C "$REPO_ROOT" cat-file -e "$HEAD_SHA:psscanner_quant/constants.py" || fail "HEAD does not contain PS Scanner source"
ARCHIVE_ROOT="$TMP_ROOT/archive"
mkdir -p "$ARCHIVE_ROOT"
git -C "$REPO_ROOT" archive --format=tar "$HEAD_SHA" | tar -xf - -C "$ARCHIVE_ROOT"
SRC="$ARCHIVE_ROOT"
ACTUAL_VERSION="$(grep -E '^VERSION = ' "$SRC/psscanner_quant/constants.py" | sed -E 's/.*"([^"]+)".*/\1/' | head -1)"
[[ "$ACTUAL_VERSION" == "$VERSION" ]] || fail "source VERSION is $ACTUAL_VERSION, expected $VERSION"

run_native(){
  echo "== Native regression =="
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "$PYTHON_BIN is required"
  command -v node >/dev/null 2>&1 || fail "node is required"
  command -v zsh >/dev/null 2>&1 || fail "zsh is required"
  cp -R "$SRC" "$TMP_ROOT/native"
  rm -rf "$TMP_ROOT/native/.git" "$TMP_ROOT/native/.github"
  "$PYTHON_BIN" -m venv "$TMP_ROOT/native-venv"
  source "$TMP_ROOT/native-venv/bin/activate"
  python -m pip install --upgrade pip
  pip install -r "$TMP_ROOT/native/requirements.txt"
  (
    cd "$TMP_ROOT/native"
    python -m compileall -q psscanner_quant tests tools
    python -c "from psscanner_quant.db import init_db; init_db()"
    python -m unittest discover -s tests -v
    python - <<'PY'
from pathlib import Path
html=Path("static/index.html").read_text()
js=html.rsplit("<script>",1)[1].split("</script>",1)[0]
Path("/tmp/ps-scanner-ui-v683.js").write_text(js)
PY
    node --check /tmp/ps-scanner-ui-v683.js
    zsh -n install.sh
    zsh -n run.sh
    python tools/check_no_secrets.py
  )
  deactivate
}

run_linux(){
  echo "== Linux regression in local container =="
  local engine=""
  if command -v docker >/dev/null 2>&1; then engine="docker";
  elif command -v podman >/dev/null 2>&1; then engine="podman";
  else fail "Docker or Podman is required for Linux parity"; fi
  "$engine" run --rm --platform "$LINUX_PLATFORM" -v "$SRC:/src:ro" python:3.12-bookworm bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq nodejs zsh >/dev/null
    cp -R /src /tmp/ps-scanner
    rm -rf /tmp/ps-scanner/.github
    cd /tmp/ps-scanner
    python -m venv /tmp/ps-venv
    . /tmp/ps-venv/bin/activate
    python -m pip install --upgrade pip >/dev/null
    pip install -r requirements.txt >/dev/null
    python -m compileall -q psscanner_quant tests tools
    python -c "from psscanner_quant.db import init_db; init_db()"
    python -m unittest discover -s tests -v
    python tools/check_no_secrets.py
    zsh -n install.sh
    zsh -n run.sh
  '
}

build_package(){
  echo "== Build tracked-source release ZIP =="
  mkdir -p "$DIST_DIR"
  local stage="$TMP_ROOT/PS_Scanner_Quant_v$VERSION"
  cp -R "$SRC" "$stage"
  rm -rf "$stage/.git" "$stage/.github"
  find "$stage" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "$stage" -type f -name '*.pyc' -delete
  local zip_path="$DIST_DIR/PS_Scanner_Quant_v$VERSION.zip"
  rm -f "$zip_path"
  (cd "$TMP_ROOT" && zip -qr "$zip_path" "PS_Scanner_Quant_v$VERSION")
  unzip -t "$zip_path" >/dev/null
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$zip_path";
  else sha256sum "$zip_path"; fi
}

run_native
run_linux
build_package
