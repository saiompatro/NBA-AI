"""Self-check for recent-form (momentum) win-probability adjustment.

Run directly: python scripts/test_recent_form.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Stub out the `app`/`app.services` packages before importing league_analytics so this
# check doesn't drag in app/__init__.py -> app.main -> torch (unrelated to this logic
# and not always installable/loadable in every environment).
for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import _FORM_POINTS_CAP, form_margin_edge


def main() -> None:
    assert form_margin_edge("5-5", "5-5") == 0.0, "even form must not move the margin"
    assert form_margin_edge("8-2", "2-8") > 0, "hotter home team must favor home"
    assert form_margin_edge("2-8", "8-2") < 0, "hotter away team must favor away"
    assert form_margin_edge("10-0", "0-10") == _FORM_POINTS_CAP, "extreme gap must cap"
    assert form_margin_edge("0-10", "10-0") == -_FORM_POINTS_CAP, "extreme gap must cap the other way"
    assert form_margin_edge("bad", "bad") == 0.0, "unparseable records must default to 0 wins each, not crash"

    print("OK: recent-form edge is symmetric, zero when even, and capped")


if __name__ == "__main__":
    main()
