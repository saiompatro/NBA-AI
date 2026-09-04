"""Self-check for the shot chart + zone efficiency aggregation.

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import (
    _SHOT_ZONE_ORDER,
    aggregate_shot_zones,
    sample_shots,
    shot_chart_params,
)


def main() -> None:
    assert aggregate_shot_zones([], []) == []

    # 5-of-10 from Mid-Range -> 50.0% for the player.
    shots = [{"zone": "Mid-Range", "made": 1} for _ in range(5)] + [{"zone": "Mid-Range", "made": 0} for _ in range(5)]
    zones = aggregate_shot_zones(shots, [])
    assert len(zones) == 1
    assert zones[0]["zone"] == "Mid-Range"
    assert zones[0]["fgm"] == 5 and zones[0]["fga"] == 10
    assert zones[0]["fg_pct"] == 50.0

    # League rows split across SHOT_ZONE_AREA with asymmetric makes/attempts must POOL,
    # not average the per-row percentages: 3/10 (30%) and 6/30 (20%) pool to 9/40 = 22.5%,
    # not the naive average of 30% and 20% (25%).
    league_rows = [
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Left Side", "FGM": 3, "FGA": 10},
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Right Side", "FGM": 6, "FGA": 30},
    ]
    zones = aggregate_shot_zones(shots, league_rows)
    assert zones[0]["league_pct"] == 22.5, f"expected pooled 22.5%, got {zones[0]['league_pct']}"
    assert zones[0]["league_pct"] != 25.0, "must not be the naive average of the two rows' percentages"

    # relative = fg_pct - league_pct, correct sign both ways.
    assert zones[0]["relative"] == round(50.0 - 22.5, 1)
    assert zones[0]["relative"] > 0, "player above league average should be positive"

    below_league_rows = [{"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Left Side", "FGM": 8, "FGA": 10}]
    below_zones = aggregate_shot_zones(shots, below_league_rows)
    assert below_zones[0]["league_pct"] == 80.0
    assert below_zones[0]["relative"] == round(50.0 - 80.0, 1)
    assert below_zones[0]["relative"] < 0, "player below league average should be negative"

    # A zone the player shot from with no matching league rows -> None, no crash.
    no_league_zones = aggregate_shot_zones(shots, [{"SHOT_ZONE_BASIC": "Backcourt", "FGM": 1, "FGA": 5}])
    assert no_league_zones[0]["league_pct"] is None
    assert no_league_zones[0]["relative"] is None

    # Output zone ordering follows _SHOT_ZONE_ORDER.
    mixed_shots = (
        [{"zone": "Backcourt", "made": 0}]
        + [{"zone": "Mid-Range", "made": 1}]
        + [{"zone": "Restricted Area", "made": 1}]
        + [{"zone": "Right Corner 3", "made": 0}]
    )
    ordered = aggregate_shot_zones(mixed_shots, [])
    zone_names = [z["zone"] for z in ordered]
    expected_order = [z for z in _SHOT_ZONE_ORDER if z in zone_names]
    assert zone_names == expected_order, f"expected {expected_order}, got {zone_names}"

    # Unknown zone names sort after every known zone, preserving encounter order among themselves.
    unknown_shots = [{"zone": "Zebra Zone", "made": 0}, {"zone": "Restricted Area", "made": 1}, {"zone": "Aardvark Zone", "made": 0}]
    unknown_zones = [z["zone"] for z in aggregate_shot_zones(unknown_shots, [])]
    assert unknown_zones == ["Restricted Area", "Zebra Zone", "Aardvark Zone"], unknown_zones

    # sample_shots truncation.
    big = [{"i": i} for i in range(900)]
    sampled = sample_shots(big, cap=500)
    assert len(sampled) == 500
    small = [{"i": i} for i in range(10)]
    assert sample_shots(small) == small

    # shot_chart_params carries every required filter key.
    params = shot_chart_params(1234, "2024-25", "Playoffs")
    assert params["ContextMeasure"] == "FGA"
    required_keys = [
        "PlayerID", "Season", "SeasonType", "TeamID", "ContextMeasure", "LeagueID",
        "Period", "LastNGames", "Month", "OpponentTeamID", "StartPeriod", "EndPeriod",
        "StartRange", "EndRange", "RangeType", "PlayerPosition", "DateFrom", "DateTo",
        "GameID", "GameSegment", "Location", "Outcome", "Position", "RookieYear",
        "SeasonSegment", "VsConference", "VsDivision", "ClutchTime", "AheadBehind",
        "PointDiff", "GameScope", "PlayerExperience",
    ]
    for key in required_keys:
        assert key in params, f"missing required shotchartdetail param: {key}"

    print("OK: shot-zone aggregation pools (not averages) league rows, signs relative correctly, handles missing league data, orders zones, sample_shots truncates to cap, and shot_chart_params carries every required filter key")


if __name__ == "__main__":
    main()
