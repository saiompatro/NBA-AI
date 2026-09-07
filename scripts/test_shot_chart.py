"""Self-check for the per-player shot chart aggregation (zone efficiency vs league
average, and the plot-point downsampler).

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

from app.services.league_analytics import SHOT_ZONE_ORDER, aggregate_shot_zones, shot_points


def _shot(zone, made, loc_x=0, loc_y=0, dist=0):
    return {
        "SHOT_ZONE_BASIC": zone,
        "SHOT_MADE_FLAG": 1 if made else 0,
        "SHOT_ATTEMPTED_FLAG": 1,
        "LOC_X": loc_x,
        "LOC_Y": loc_y,
        "SHOT_DISTANCE": dist,
    }


def main() -> None:
    shots = [
        # Restricted Area: 4/6
        *[_shot("Restricted Area", made) for made in (True, True, True, True, False, False)],
        # Mid-Range: 2/5
        *[_shot("Mid-Range", made) for made in (True, True, False, False, False)],
        # Above the Break 3: 3/8 (a 3pt zone -> PPS should be 3-weighted)
        *[_shot("Above the Break 3", made) for made in (True, True, True, False, False, False, False, False)],
        # Backcourt heave: must never appear in the output
        _shot("Backcourt", False),
    ]

    # LeagueAverages splits "Above the Break 3" across multiple SHOT_ZONE_AREA rows -
    # these must be pooled (FGM/FGA summed) before computing a league FG%, not averaged
    # as percentages (which would give a materially different, wrong answer here).
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGM": 500, "FGA": 800},
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Center(C)", "FGM": 200, "FGA": 500},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_ZONE_AREA": "Left Side Center(LC)", "FGM": 10, "FGA": 100},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_ZONE_AREA": "Right Side Center(RC)", "FGM": 10, "FGA": 100},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_ZONE_AREA": "Center(C)", "FGM": 80, "FGA": 200},
        # A league zone with zero attempts must not crash the pooling/division logic.
        {"SHOT_ZONE_BASIC": "Left Corner 3", "SHOT_ZONE_AREA": "Left Side(L)", "FGM": 0, "FGA": 0},
    ]

    zones = aggregate_shot_zones(shots, league_rows)

    # Backcourt must never surface, and only zones with fga > 0 should be present.
    zone_names = [z["zone"] for z in zones]
    assert "Backcourt" not in zone_names, "backcourt heaves must never appear in zone output"
    assert "Left Corner 3" not in zone_names, "zero-attempt zones must be omitted"
    assert "Right Corner 3" not in zone_names, "zones with no shots at all must be omitted"

    # Order must follow SHOT_ZONE_ORDER, not input order.
    expected_order = [z for z in SHOT_ZONE_ORDER if z in zone_names]
    assert zone_names == expected_order, f"zone order must match SHOT_ZONE_ORDER, got {zone_names}"

    by_zone = {z["zone"]: z for z in zones}

    ra = by_zone["Restricted Area"]
    assert ra["fga"] == 6 and ra["fgm"] == 4, "restricted area fga/fgm must match input shots"
    assert ra["fg_pct"] == 66.7, f"expected 66.7 fg_pct, got {ra['fg_pct']}"
    assert ra["is_three"] is False
    assert ra["pps"] == round((4 * 2) / 6, 2), "2pt zone PPS must be 2-weighted"
    # League: 500/800 = 62.5%
    assert ra["league_pct"] == 62.5, f"expected pooled league pct 62.5, got {ra['league_pct']}"
    assert ra["delta"] == round(66.7 - 62.5, 1), "delta must be fg_pct - league_pct"

    mr = by_zone["Mid-Range"]
    assert mr["fga"] == 5 and mr["fgm"] == 2
    assert mr["is_three"] is False
    assert mr["pps"] == round((2 * 2) / 5, 2)

    atb3 = by_zone["Above the Break 3"]
    assert atb3["fga"] == 8 and atb3["fgm"] == 3
    assert atb3["is_three"] is True, "Above the Break 3 must be flagged as a three-point zone"
    assert atb3["pps"] == round((3 * 3) / 8, 2), "3pt zone PPS must be 3-weighted"
    # Pooled league FG% for Above the Break 3: (10+10+80) / (100+100+200) = 100/400 = 25.0%
    # NOT the average of the three area percentages (10%, 10%, 40% -> would average to 20%).
    assert atb3["league_pct"] == 25.0, f"league pct must be pooled (FGM/FGA), got {atb3['league_pct']}"
    assert atb3["league_pct"] != 20.0, "league pct must never be an average of per-area percentages"

    # share% is this zone's fga over total fga across all (non-backcourt) zones: 6+5+8=19
    total_fga = 19
    assert ra["share"] == round((6 / total_fga) * 100, 1)
    assert mr["share"] == round((5 / total_fga) * 100, 1)
    assert atb3["share"] == round((8 / total_fga) * 100, 1)

    # Empty input must never crash and must return an empty list.
    assert aggregate_shot_zones([], []) == []
    assert aggregate_shot_zones([], league_rows) == []

    # A league zone with FGA == 0 (Left Corner 3 above) must not raise ZeroDivisionError
    # even when a player *did* shoot from that zone.
    shots_with_corner = shots + [_shot("Left Corner 3", True)]
    zones_with_corner = aggregate_shot_zones(shots_with_corner, league_rows)
    corner = next(z for z in zones_with_corner if z["zone"] == "Left Corner 3")
    assert corner["league_pct"] == 0, "a zero-FGA league zone must report 0 league_pct, not crash"
    assert corner["fga"] == 1 and corner["fgm"] == 1

    # --- shot_points -------------------------------------------------------
    raw_points = [
        {"LOC_X": i, "LOC_Y": 100, "SHOT_MADE_FLAG": i % 2, "SHOT_DISTANCE": 10}
        for i in range(20)
    ]
    # A backcourt heave (LOC_Y > 400) must be dropped.
    raw_points.append({"LOC_X": 0, "LOC_Y": 450, "SHOT_MADE_FLAG": 1, "SHOT_DISTANCE": 45})
    # Bad/missing data must be skipped defensively, never crash the call.
    raw_points.append({"LOC_X": "not-a-number", "LOC_Y": 100, "SHOT_MADE_FLAG": 1, "SHOT_DISTANCE": 10})
    raw_points.append({"LOC_X": 0, "SHOT_MADE_FLAG": 1, "SHOT_DISTANCE": 10})  # missing LOC_Y

    capped = shot_points(raw_points, limit=5)
    assert len(capped) == 5, f"expected downsample to 5 points, got {len(capped)}"
    for point in capped:
        assert isinstance(point["x"], int) and isinstance(point["y"], int) and isinstance(point["d"], int)
        assert isinstance(point["made"], bool)
        assert point["y"] <= 400, "backcourt heaves (LOC_Y > 400) must never appear in shot_points output"

    uncapped = shot_points(raw_points, limit=500)
    assert len(uncapped) == 20, "valid, non-backcourt points must all survive when under the limit"

    assert shot_points([]) == []

    print("OK: shot-chart zone aggregation and point downsampling are internally consistent")


if __name__ == "__main__":
    main()
