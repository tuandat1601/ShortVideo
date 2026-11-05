"""Cầu nối tới code cũ trong long-tieng/ (tái dùng, không viết lại)."""
from __future__ import annotations

import sys
from pathlib import Path

LEGACY = Path(__file__).resolve().parents[2] / "long-tieng"


def use_legacy() -> Path:
    p = str(LEGACY)
    if p not in sys.path:
        sys.path.insert(0, p)
    return LEGACY
