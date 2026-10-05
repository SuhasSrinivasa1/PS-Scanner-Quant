from __future__ import annotations

import os
from pathlib import Path

from .paths import ROOT


def _load_build_commit() -> str:
    """Load CI-packaged commit once; request paths stay filesystem-free."""
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


BUILD_COMMIT=_load_build_commit()


def build_commit() -> str:
    return BUILD_COMMIT
