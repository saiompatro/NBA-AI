"""Self-check for shot-chart zone aggregation.

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

from app.services.league_analytics import aggregate_shot_zones


def main() -> None:
    assert aggregate_shot_zones([]) == [], "no shots must aggregate to no zones"

    records = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_MADE_FLAG": 1, "SHOT_TYPE": "2PT Field Goal"},
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_MADE_FLAG": 0, "SHOT_TYPE": "2PT Field Goal"},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_MADE_FLAG": 1, "SHOT_TYPE": "3PT Field Goal"},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_MADE_FLAG": 0, "SHOT_TYPE": "3PT Field Goal"},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_MADE_FLAG": 0, "SHOT_TYPE": "3PT Field Goal"},
    ]
    zones = aggregate_shot_zones(records)
    by_zone = {row["zone"]: row for row in zones}

    restricted = by_zone["Restricted Area"]
    assert restricted["fga"] == 2 and restricted["fgm"] == 1
    assert restricted["fg_pct"] == 50.0, "1-for-2 must be exactly 50% FG"
    assert restricted["pts_per_shot"] == 1.0, "one 2pt make on 2 attempts is 1.0 pts/shot"

    above_break = by_zone["Above the Break 3"]
    assert above_break["fga"] == 3 and above_break["fgm"] == 1
    assert round(above_break["fg_pct"], 1) == round(100 / 3, 1)
    assert round(above_break["pts_per_shot"], 2) == 1.0, "one 3pt make on 3 attempts is 1.0 pts/shot"

    # Rows must be sorted by attempt volume, most-attempted zone first.
    assert zones[0]["zone"] == "Above the Break 3", "the 3-attempt zone must sort before the 2-attempt zone"

    # Missing/blank zone labels fall back to a single "Unknown" bucket instead of crashing.
    unknown = aggregate_shot_zones([{"SHOT_MADE_FLAG": 1, "SHOT_TYPE": "2PT Field Goal"}])
    assert unknown[0]["zone"] == "Unknown"

    # A zone with zero attempts is never emitted (division-by-zero safety is for
    # completeness in aggregate_shot_zones' own math, not a reachable input here).
    print("OK: shot-zone aggregation math is correct, sorted, and null-safe")


if __name__ == "__main__":
    main()
