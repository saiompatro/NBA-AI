"""Self-check for the shot-chart per-zone summary helper (FGM/FGA/FG% vs. league average).

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

from app.services.league_analytics import summarize_shot_zones


def _shot(zone: str, made: bool) -> dict:
    return {"zone": zone, "made": made}


def main() -> None:
    # --- correct FGM/FGA/FG% per zone, correct sign on the vs-league diff ---
    shots = [
        _shot("Restricted Area", True),
        _shot("Restricted Area", True),
        _shot("Restricted Area", False),
        _shot("Restricted Area", False),
        _shot("Above the Break 3", True),
        _shot("Above the Break 3", False),
        _shot("Above the Break 3", False),
        _shot("Above the Break 3", False),
    ]
    league_averages = {
        "Restricted Area": 0.60,  # league shoots 60% there; player shoots 50% -> negative diff
        "Above the Break 3": 0.20,  # league shoots 20% there; player shoots 25% -> positive diff
    }
    zones = summarize_shot_zones(shots, league_averages)
    by_zone = {row["zone"]: row for row in zones}

    restricted = by_zone["Restricted Area"]
    assert restricted["fgm"] == 2, "2 makes in the restricted area"
    assert restricted["fga"] == 4, "4 attempts in the restricted area"
    assert restricted["fg_pct"] == 50.0, f"expected 50.0% FG, got {restricted['fg_pct']}"
    assert restricted["league_fg_pct"] == 60.0
    assert restricted["diff"] < 0, "player shoots worse than league here -> diff must be negative"
    assert restricted["diff"] == -10.0, f"expected -10.0 diff, got {restricted['diff']}"

    three = by_zone["Above the Break 3"]
    assert three["fgm"] == 1 and three["fga"] == 4
    assert three["fg_pct"] == 25.0
    assert three["diff"] > 0, "player shoots better than league here -> diff must be positive"
    assert three["diff"] == 5.0, f"expected 5.0 diff, got {three['diff']}"

    # --- empty-input handling ---
    assert summarize_shot_zones([], {}) == [], "no shots, no league data -> empty zone list"
    assert summarize_shot_zones([], {"Mid-Range": 0.41}) == [
        {"zone": "Mid-Range", "fgm": 0, "fga": 0, "fg_pct": 0.0, "league_fg_pct": 41.0, "diff": -41.0}
    ], "a league zone with zero player shots must still appear, at 0 FGA/0 FG%"

    # --- no division-by-zero on a zone with 0 FGA (mixed with zones that do have shots) ---
    mixed_zones = summarize_shot_zones(
        [_shot("Mid-Range", True)],
        {"Mid-Range": 0.40, "Left Corner 3": 0.38},
    )
    by_zone2 = {row["zone"]: row for row in mixed_zones}
    left_corner = by_zone2["Left Corner 3"]
    assert left_corner["fga"] == 0 and left_corner["fgm"] == 0
    assert left_corner["fg_pct"] == 0.0, "zero attempts must not raise ZeroDivisionError and must report 0.0%"
    assert left_corner["league_fg_pct"] == 38.0
    assert left_corner["diff"] == -38.0

    # A zone with shots but not in league_averages should default league_fg_pct to 0.
    no_league_data = summarize_shot_zones([_shot("Backcourt", False)], {})
    assert no_league_data[0]["league_fg_pct"] == 0.0
    assert no_league_data[0]["fg_pct"] == 0.0
    assert no_league_data[0]["diff"] == 0.0

    print("OK: shot-chart zone summary is internally consistent (FGM/FGA/FG%, diff sign, no div-by-zero)")


if __name__ == "__main__":
    main()
