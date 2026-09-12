"""Self-check for shot-chart zone aggregation and its fallback (no network).

Run directly: python scripts/test_shot_chart.py
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

from app.services.league_analytics import aggregate_shot_zones, shot_chart_fallback


def _shots(zone: str, makes: int, misses: int) -> list[dict]:
    return [{"zone": zone, "made": True} for _ in range(makes)] + [
        {"zone": zone, "made": False} for _ in range(misses)
    ]


def main() -> None:
    shots = _shots("Above the Break 3", 4, 6) + _shots("Mid-Range", 4, 6)
    zones = {row["zone"]: row for row in aggregate_shot_zones(shots, {"Above the Break 3": 0.35, "Mid-Range": 0.42})}

    atb3 = zones["Above the Break 3"]
    assert atb3["fga"] == 10 and atb3["fgm"] == 4
    assert atb3["fg_pct"] == 40.0, "4/10 must be 40% FG"
    assert atb3["pps"] == 1.2, "4/10 at 3pt value must be 1.2 points per shot"
    assert atb3["diff"] > 0, "40% beats a 35% league average -> positive diff"

    mid = zones["Mid-Range"]
    assert mid["pps"] == 0.8, "4/10 at 2pt value must be 0.8 points per shot"
    assert mid["diff"] < 0, "40% trails a 42% league average -> negative diff"

    empty_zone = zones["Restricted Area"]
    assert empty_zone["fga"] == 0 and empty_zone["fg_pct"] == 0.0, "zero attempts must not raise or fabricate a percentage"

    fallback_hot = shot_chart_fallback(fg_pct=55.0, fg3_pct=38.0)
    fallback_cold = shot_chart_fallback(fg_pct=40.0, fg3_pct=32.0)
    assert fallback_hot["source"] == "fallback"
    expected_zones = {
        "Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
        "Left Corner 3", "Right Corner 3", "Above the Break 3",
    }
    assert set(fallback_hot["zones"]) == expected_zones, "fallback must cover every shot zone"
    assert fallback_hot["zones"]["Restricted Area"] > fallback_cold["zones"]["Restricted Area"], \
        "a better overall shooter must also fall back to a hotter restricted-area estimate"

    print("OK: shot-chart zone aggregation and fallback are internally consistent")


if __name__ == "__main__":
    main()
