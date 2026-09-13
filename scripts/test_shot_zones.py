"""Self-check for the shot-location zone profile (frequency/FG%/points-per-shot by zone).

Run directly: python scripts/test_shot_zones.py
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

from app.services.league_analytics import (
    parse_shot_location_columns,
    shot_zone_fallback,
    shot_zone_profile,
)

# Real leaguedashteamshotlocations header shape (nba_api's own documented example).
_HEADERS = [
    {
        "name": "SHOT_CATEGORY",
        "columnSpan": 3,
        "columnsToSkip": 2,
        "columnNames": [
            "Restricted Area",
            "In The Paint (Non-RA)",
            "Mid-Range",
            "Left Corner 3",
            "Right Corner 3",
            "Above the Break 3",
            "Backcourt",
        ],
    },
    {
        "name": "columns",
        "columnSpan": 1,
        "columnNames": ["TEAM_ID", "TEAM_NAME"] + ["FGM", "FGA", "FG_PCT"] * 7,
    },
]


def main() -> None:
    columns = parse_shot_location_columns(_HEADERS)
    assert columns[:2] == ["TEAM_ID", "TEAM_NAME"], "leading columns must stay untouched"
    assert len(columns) == 23, "2 id columns + 7 zones x 3 metrics = 23 flat columns"
    assert columns[2:5] == ["RESTRICTED_AREA_FGM", "RESTRICTED_AREA_FGA", "RESTRICTED_AREA_FG_PCT"]
    assert columns[8:11] == ["MID_RANGE_FGM", "MID_RANGE_FGA", "MID_RANGE_FG_PCT"]
    assert len(set(columns)) == len(columns), "flattened columns must be unique"
    assert parse_shot_location_columns([]) == [], "a malformed/empty header must not crash"

    # Fabricate a team row using the flattened columns: heavy rim/three, average mid-range.
    zone_totals = {
        "RESTRICTED_AREA_FGM": 300, "RESTRICTED_AREA_FGA": 500, "RESTRICTED_AREA_FG_PCT": 0.6,
        "IN_THE_PAINT_NON_RA_FGM": 60, "IN_THE_PAINT_NON_RA_FGA": 150, "IN_THE_PAINT_NON_RA_FG_PCT": 0.4,
        "MID_RANGE_FGM": 40, "MID_RANGE_FGA": 100, "MID_RANGE_FG_PCT": 0.4,
        "LEFT_CORNER_3_FGM": 30, "LEFT_CORNER_3_FGA": 75, "LEFT_CORNER_3_FG_PCT": 0.4,
        "RIGHT_CORNER_3_FGM": 30, "RIGHT_CORNER_3_FGA": 75, "RIGHT_CORNER_3_FG_PCT": 0.4,
        "ABOVE_THE_BREAK_3_FGM": 120, "ABOVE_THE_BREAK_3_FGA": 400, "ABOVE_THE_BREAK_3_FG_PCT": 0.3,
        "BACKCOURT_FGM": 0, "BACKCOURT_FGA": 5, "BACKCOURT_FG_PCT": 0.0,
    }
    profile = shot_zone_profile(zone_totals)
    assert {row["key"] for row in profile} == {"rim", "paint", "midrange", "corner3", "atb3"}, "backcourt is dropped"
    corner3 = next(row for row in profile if row["key"] == "corner3")
    assert corner3["fga"] == 150.0, "left + right corner 3 must merge into one row"
    assert corner3["fg_pct"] == 40.0
    assert corner3["pps"] == 1.2, "points-per-shot on a made 3 is fg_pct * 3"
    total_freq = round(sum(row["freq"] for row in profile), 1)
    assert 99.0 <= total_freq <= 100.0, f"zone frequencies (backcourt excluded) must sum to ~100%, got {total_freq}"

    empty_profile = shot_zone_profile({})
    assert all(row["fga"] == 0 and row["freq"] == 0 and row["pps"] == 0 for row in empty_profile), "zero-FGA must not crash or divide by zero"

    # Fallback must use the same row shape as a live profile and track eFG% direction.
    league_avg = shot_zone_fallback(53.0)
    assert {row["key"] for row in league_avg} == {row["key"] for row in profile}
    assert round(sum(row["freq"] for row in league_avg), 1) == 100.0

    above_avg = shot_zone_fallback(58.0)
    below_avg = shot_zone_fallback(48.0)
    rim_avg = next(row for row in league_avg if row["key"] == "rim")["fg_pct"]
    rim_above = next(row for row in above_avg if row["key"] == "rim")["fg_pct"]
    rim_below = next(row for row in below_avg if row["key"] == "rim")["fg_pct"]
    assert rim_above > rim_avg > rim_below, "a better team eFG% must scale every fallback zone's FG% up"

    zero_efg = shot_zone_fallback(0.0)
    assert zero_efg, "a falsy eFG% (0.0) must fall back to the neutral (scale=1.0) shape, not crash"

    print("OK: shot-zone profile parsing/merging/fallback are internally consistent")


if __name__ == "__main__":
    main()
