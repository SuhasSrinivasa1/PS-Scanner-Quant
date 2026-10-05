from __future__ import annotations

import os
from pathlib import Path

from .paths import ROOT


def build_commit() -> str:
    """Return the CI-packaged Git commit without requiring a .git directory."""
    env=str(os.environ.get("PS_SCANNER_BUILD_COMMIT") or "").strip()
    if env:
        return env
    p=Path(ROOT)/"BUILD_COMMIT"
    try:
        value=p.read_text().strip()
        if value:
            return value
    except Exception:
        pass
    return "SOURCE_TREE"
