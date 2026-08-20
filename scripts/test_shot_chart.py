"""Self-check for the player shot-chart helpers (shot normalization + zone FG%
vs league average).

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

import pandas as pd

from app.services.league_analytics import normalize_shot_rows, shot_zone_summary


def _shots_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def main() -> None:
    # --- normalize_shot_rows: made-flag mapping, x/y passthrough, column selection ---
    raw_rows = [
        {"LOC_X": -50, "LOC_Y": 20, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Mid-Range",
         "SHOT_ZONE_AREA": "Left Side(L)", "SHOT_DISTANCE": 12, "PERIOD": 1},
        {"LOC_X": 0, "LOC_Y": 5, "SHOT_MADE_FLAG": 0, "SHOT_ZONE_BASIC": "Restricted Area",
         "SHOT_ZONE_AREA": "Center(C)", "SHOT_DISTANCE": 1, "PERIOD": 2},
        {"LOC_X": 230, "LOC_Y": 80, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Left Corner 3",
         "SHOT_ZONE_AREA": "Left Side(L)", "SHOT_DISTANCE": 23, "PERIOD": 3},
    ]
    frame = _shots_frame(raw_rows)
    shots = normalize_shot_rows(frame)
    assert len(shots) == 3, "all rows should be kept when under the limit"
    assert shots[0]["x"] == -50 and shots[0]["y"] == 20, "x/y must pass through unchanged"
    assert shots[0]["made"] is True, "SHOT_MADE_FLAG=1 must map to made=True"
    assert shots[1]["made"] is False, "SHOT_MADE_FLAG=0 must map to made=False"
    assert shots[0]["zone"] == "Mid-Range"
    assert shots[2]["area"] == "Left Side(L)"
    assert shots[2]["distance"] == 23
    assert shots[2]["period"] == 3

    # --- normalize_shot_rows: limit row-cap is honored, keeping the most recent rows ---
    many_rows = [
        {"LOC_X": i, "LOC_Y": i, "SHOT_MADE_FLAG": i % 2, "SHOT_ZONE_BASIC": "Mid-Range",
         "SHOT_ZONE_AREA": "Center(C)", "SHOT_DISTANCE": 10, "PERIOD": 1}
        for i in range(10)
    ]
    capped = normalize_shot_rows(_shots_frame(many_rows), limit=4)
    assert len(capped) == 4, "limit must cap the number of returned shots"
    assert [shot["x"] for shot in capped] == [6, 7, 8, 9], "cap must keep the most recent rows (the tail)"

    # --- normalize_shot_rows: empty input frame is handled without raising ---
    empty_shots = normalize_shot_rows(pd.DataFrame())
    assert empty_shots == [], "an empty frame must produce an empty shot list, not raise"

    # --- shot_zone_summary: per-zone FGM/FGA/FG% arithmetic and diff sign ---
    player_shots = [
        {"x": 0, "y": 5, "made": True, "zone": "Restricted Area", "area": "Center(C)", "distance": 1, "period": 1},
        {"x": 5, "y": 8, "made": True, "zone": "Restricted Area", "area": "Center(C)", "distance": 1, "period": 1},
        {"x": -5, "y": 6, "made": False, "zone": "Restricted Area", "area": "Center(C)", "distance": 1, "period": 1},
        {"x": -50, "y": 20, "made": True, "zone": "Mid-Range", "area": "Left Side(L)", "distance": 12, "period": 2},
        {"x": -60, "y": 22, "made": False, "zone": "Mid-Range", "area": "Left Side(L)", "distance": 13, "period": 2},
        {"x": -70, "y": 25, "made": False, "zone": "Mid-Range", "area": "Left Side(L)", "distance": 14, "period": 2},
        {"x": -80, "y": 28, "made": False, "zone": "Mid-Range", "area": "Left Side(L)", "distance": 15, "period": 3},
    ]
    league_rows = [
        # Restricted Area: league FGM=60, FGA=100 across two zone/range rows -> 60.0%
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGA": 60, "FGM": 40},
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGA": 40, "FGM": 20},
        # Mid-Range: league FGM=40, FGA=100 -> 40.0%
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Left Side(L)", "FGA": 100, "FGM": 40},
    ]
    league_frame = pd.DataFrame(league_rows)

    zones = shot_zone_summary(player_shots, league_frame)
    by_zone = {row["zone"]: row for row in zones}

    restricted = by_zone["Restricted Area"]
    assert restricted["fga"] == 3 and restricted["fgm"] == 2
    assert restricted["fg_pct"] == round(2 / 3 * 100, 1), "player FG% arithmetic must be FGM/FGA"
    assert restricted["league_pct"] == 60.0, "league FG% must be summed FGM/FGA across the zone's rows"
    assert restricted["diff"] == round(restricted["fg_pct"] - 60.0, 1), "diff must be player fg_pct minus league_pct"
    assert restricted["diff"] > 0, "player shooting better than league must give a positive diff"

    mid_range = by_zone["Mid-Range"]
    assert mid_range["fga"] == 4 and mid_range["fgm"] == 1
    assert mid_range["fg_pct"] == 25.0
    assert mid_range["league_pct"] == 40.0
    assert mid_range["diff"] == round(25.0 - 40.0, 1)
    assert mid_range["diff"] < 0, "player shooting worse than league must give a negative diff"

    # --- shot_zone_summary: empty shots produce an empty zone list without raising ---
    assert shot_zone_summary([], league_frame) == [], "no shots must produce an empty zone summary, not raise"

    # --- empty-data path: an empty shots frame means the chart is unavailable, no raise ---
    assert normalize_shot_rows(pd.DataFrame()) == [], "empty shot frame must not raise and must yield no shots"

    print("OK: shot-chart normalization and zone-summary arithmetic are correct")


if __name__ == "__main__":
    main()
