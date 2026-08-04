"""Self-check for advanced team-stats fallback (off/def rating, pace, four factors).

Run directly: python scripts/test_advanced_stats.py
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

from app.services.league_analytics import advanced_fallback


def main() -> None:
    even = advanced_fallback(0.0)
    assert even["off_rtg"] == even["def_rtg"], "a net-neutral team must have equal off/def rating"

    strong = advanced_fallback(10.0)
    weak = advanced_fallback(-10.0)
    assert strong["off_rtg"] - strong["def_rtg"] == 10.0, "fallback ratings must reproduce the net rating"
    assert weak["off_rtg"] - weak["def_rtg"] == -10.0, "fallback ratings must reproduce a negative net rating too"
    assert strong["off_rtg"] > weak["off_rtg"], "a better net rating must mean a better fallback offense"
    assert strong["def_rtg"] < weak["def_rtg"], "a better net rating must mean a better (lower) fallback defense"

    for stats in (even, strong, weak):
        assert stats["pace"] == 99.5, "pace fallback is a fixed league-average stand-in"
        assert set(stats) == {"off_rtg", "def_rtg", "pace", "efg_pct", "ts_pct", "tov_pct"}

    print("OK: advanced-stats fallback is internally consistent with net rating")


if __name__ == "__main__":
    main()
