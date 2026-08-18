"""Self-check for player shot-chart normalization/aggregation
(app.services.league_analytics.shot_chart_rows / shot_chart_zones).

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

from app.services.league_analytics import shot_chart_rows, shot_chart_zones


def main() -> None:
    # 1. A made 2pt restricted-area shot and a missed 3pt above-the-break shot
    #    normalize correctly.
    made_2pt = {
        "LOC_X": "10", "LOC_Y": "5", "SHOT_DISTANCE": "1", "PERIOD": "1",
        "SHOT_MADE_FLAG": "1", "SHOT_ZONE_BASIC": "Restricted Area", "SHOT_TYPE": "2PT Field Goal",
    }
    missed_3pt = {
        "LOC_X": "-220", "LOC_Y": "60", "SHOT_DISTANCE": "24", "PERIOD": "2",
        "SHOT_MADE_FLAG": "0", "SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_TYPE": "3PT Field Goal",
    }
    rows = shot_chart_rows([made_2pt, missed_3pt])
    assert len(rows) == 2, "both valid records should normalize"
    assert rows[0]["made"] is True and rows[0]["value"] == 2 and rows[0]["zone"] == "Restricted Area"
    assert rows[1]["made"] is False and rows[1]["value"] == 3 and rows[1]["zone"] == "Above the Break 3"

    # 2. Coordinate clamping.
    clamp_records = [
        {"LOC_X": "0", "LOC_Y": "750", "SHOT_DISTANCE": "40", "PERIOD": "1", "SHOT_MADE_FLAG": "0", "SHOT_ZONE_BASIC": "Backcourt", "SHOT_TYPE": "2PT Field Goal"},
        {"LOC_X": "-400", "LOC_Y": "50", "SHOT_DISTANCE": "40", "PERIOD": "1", "SHOT_MADE_FLAG": "1", "SHOT_ZONE_BASIC": "Left Corner 3", "SHOT_TYPE": "3PT Field Goal"},
    ]
    clamped = shot_chart_rows(clamp_records)
    assert len(clamped) == 2
    assert clamped[0]["y"] == 417.5, "LOC_Y=750 must clamp to the halfcourt bound (417.5)"
    assert clamped[1]["x"] == -250.0, "LOC_X=-400 must clamp to the left court bound (-250)"
    for row in shot_chart_rows([made_2pt, missed_3pt] + clamp_records):
        assert -250 <= row["x"] <= 250, f"x out of court bounds: {row}"
        assert -52.5 <= row["y"] <= 417.5, f"y out of court bounds: {row}"

    # 3. Non-numeric / missing coordinates are skipped, not raised.
    bad_records = [
        {"LOC_X": None, "LOC_Y": "10", "SHOT_DISTANCE": "5", "PERIOD": "1", "SHOT_MADE_FLAG": "1", "SHOT_ZONE_BASIC": "Mid-Range", "SHOT_TYPE": "2PT Field Goal"},
        {"LOC_X": "abc", "LOC_Y": "10", "SHOT_DISTANCE": "5", "PERIOD": "1", "SHOT_MADE_FLAG": "1", "SHOT_ZONE_BASIC": "Mid-Range", "SHOT_TYPE": "2PT Field Goal"},
    ]
    skipped = shot_chart_rows(bad_records)
    assert skipped == [], "records with unusable LOC_X must be skipped, not raise"
    mixed = shot_chart_rows(bad_records + [made_2pt])
    assert len(mixed) == 1 and mixed[0]["zone"] == "Restricted Area"

    # 4. Zone aggregation: 3 restricted-area attempts (2 made, value 2), 2 three-point
    #    attempts (1 made, value 3).
    fixture = [
        {"x": 0, "y": 5, "made": True, "zone": "Restricted Area", "dist": 1, "period": 1, "value": 2},
        {"x": 5, "y": 6, "made": True, "zone": "Restricted Area", "dist": 1, "period": 1, "value": 2},
        {"x": -5, "y": 4, "made": False, "zone": "Restricted Area", "dist": 1, "period": 1, "value": 2},
        {"x": 220, "y": 60, "made": True, "zone": "Above the Break 3", "dist": 24, "period": 2, "value": 3},
        {"x": -220, "y": 60, "made": False, "zone": "Above the Break 3", "dist": 24, "period": 2, "value": 3},
    ]
    zones = shot_chart_zones(fixture)
    by_zone = {z["zone"]: z for z in zones}
    ra = by_zone["Restricted Area"]
    assert ra["made"] == 2 and ra["attempts"] == 3
    assert ra["fg_pct"] == round(2 / 3 * 100, 1)
    assert ra["pps"] == round((2 * 2) / 3, 2), "pps must be points/attempts, not derived from fg_pct"
    atb = by_zone["Above the Break 3"]
    assert atb["made"] == 1 and atb["attempts"] == 2
    assert atb["fg_pct"] == 50.0
    assert atb["pps"] == round(3 / 2, 2), "pps must be points/attempts, not derived from fg_pct"

    # 5. Zones sorted by attempts descending; attempts sum to len(rows).
    assert [z["zone"] for z in zones] == ["Restricted Area", "Above the Break 3"]
    assert sum(z["attempts"] for z in zones) == len(fixture)

    # 6. Empty input.
    assert shot_chart_rows([]) == []
    assert shot_chart_zones([]) == []

    print("OK: shot-chart normalization and zone aggregation are correct")


if __name__ == "__main__":
    main()
