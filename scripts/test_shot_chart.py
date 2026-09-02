"""Self-check for the player shot chart (zone aggregation, league-average pooling,
fallback, and truncation).

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

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
    _SHOT_CHART_MAX_POINTS,
    LeagueAnalyticsService,
    aggregate_shot_zones,
    shot_chart_fallback,
)


def _frames(shots_rows: list[dict], league_rows: list[dict]) -> dict[str, pd.DataFrame]:
    return {"Shot_Chart_Detail": pd.DataFrame(shots_rows), "LeagueAverages": pd.DataFrame(league_rows)}


_EMPTY_FRAMES = {"Shot_Chart_Detail": pd.DataFrame(), "LeagueAverages": pd.DataFrame()}


def _shot_row(x: float, y: float, made: int, shot_type: str, zone: str) -> dict:
    return {
        "LOC_X": x,
        "LOC_Y": y,
        "SHOT_MADE_FLAG": made,
        "SHOT_ATTEMPTED_FLAG": 1,
        "SHOT_TYPE": shot_type,
        "SHOT_ZONE_BASIC": zone,
        "PLAYER_NAME": "Test Player",
        "TEAM_NAME": "Test Team",
    }


def test_zone_math_and_league_pooling() -> None:
    shots_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_MADE_FLAG": 1, "SHOT_ATTEMPTED_FLAG": 1},
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_MADE_FLAG": 0, "SHOT_ATTEMPTED_FLAG": 1},
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_MADE_FLAG": 1, "SHOT_ATTEMPTED_FLAG": 1},
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_MADE_FLAG": 0, "SHOT_ATTEMPTED_FLAG": 1},
        {"SHOT_ZONE_BASIC": "Backcourt", "SHOT_MADE_FLAG": 0, "SHOT_ATTEMPTED_FLAG": 1},
    ]
    # Restricted Area league average split across two SHOT_ZONE_AREA rows: pooling
    # must sum both (420/740 = 56.8%), not just take the first row (400/700 = 57.1%).
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGM": 400, "FGA": 700},
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Left Side(L)", "FGM": 20, "FGA": 40},
        {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Center(C)", "FGM": 150, "FGA": 400},
    ]

    zones = aggregate_shot_zones(shots_rows, league_rows)
    zone_names = [zone["zone"] for zone in zones]
    assert "Backcourt" not in zone_names, "Backcourt must be excluded from the zone table"

    restricted = next(zone for zone in zones if zone["zone"] == "Restricted Area")
    assert restricted["fgm"] == 2 and restricted["fga"] == 3, "player makes/attempts must sum correctly per zone"
    pooled_pct = round((400 + 20) / (700 + 40) * 100, 1)
    first_row_only_pct = round(400 / 700 * 100, 1)
    assert restricted["league_fg_pct"] == pooled_pct, "league average must pool every SHOT_ZONE_AREA row"
    assert restricted["league_fg_pct"] != first_row_only_pct, "league average must not equal a single sub-zone's row"
    assert restricted["diff"] > 0, "shooting above the pooled league average must give a positive diff"

    mid_range = next(zone for zone in zones if zone["zone"] == "Mid-Range")
    assert mid_range["diff"] < 0, "0-for-1 mid-range against a 37.5% league average must give a negative diff"

    print("OK: zone aggregation math and league-average pooling are correct")


def test_shot_type_mapping_and_totals() -> None:
    shots_rows = [
        _shot_row(0, 10, 1, "2PT Field Goal", "Restricted Area"),
        _shot_row(220, 80, 0, "3PT Field Goal", "Right Corner 3"),
        _shot_row(-30, 300, 1, "3PT Field Goal", "Above the Break 3"),
    ]
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGM": 400, "FGA": 700},
        {"SHOT_ZONE_BASIC": "Right Corner 3", "SHOT_ZONE_AREA": "Right Side(R)", "FGM": 50, "FGA": 120},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_ZONE_AREA": "Center(C)", "FGM": 300, "FGA": 850},
    ]
    frames = {"Playoffs": _EMPTY_FRAMES, "Regular Season": _frames(shots_rows, league_rows)}
    service = LeagueAnalyticsService()
    object.__setattr__(service, "_shot_chart_frames", lambda pid, season, season_type: frames[season_type])

    result = service.shot_chart(101, "2025-26")
    assert result["season_type"] == "Regular Season", "an empty Playoffs frame must fall back to Regular Season"

    totals = result["totals"]
    assert totals["fga"] == 3 and totals["fgm"] == 2
    assert totals["fg3a"] == 2, "fg3a must only count 3PT Field Goal rows"
    assert totals["fg3m"] == 1

    v_values = {shot["v"] for shot in result["shots"]}
    assert v_values == {2, 3}, "shots must carry v=2 for 2PT rows and v=3 for 3PT rows"
    made_by_v = {(shot["v"], shot["m"]) for shot in result["shots"]}
    assert (2, 1) in made_by_v and (3, 0) in made_by_v and (3, 1) in made_by_v

    print("OK: SHOT_TYPE maps to v correctly and totals.fg3a only counts 3PT rows")


def test_backcourt_excluded_but_counted_in_totals() -> None:
    shots_rows = [
        _shot_row(0, 10, 1, "2PT Field Goal", "Restricted Area"),
        _shot_row(0, 800, 0, "3PT Field Goal", "Backcourt"),
    ]
    league_rows = [{"SHOT_ZONE_BASIC": "Restricted Area", "SHOT_ZONE_AREA": "Center(C)", "FGM": 400, "FGA": 700}]
    frames = {"Playoffs": _frames(shots_rows, league_rows), "Regular Season": _EMPTY_FRAMES}
    service = LeagueAnalyticsService()
    object.__setattr__(service, "_shot_chart_frames", lambda pid, season, season_type: frames[season_type])

    result = service.shot_chart(102, "2025-26")
    assert result["totals"]["fga"] == 2, "Backcourt attempts must still count toward totals.fga"
    assert "Backcourt" not in [zone["zone"] for zone in result["zones"]], "Backcourt must not appear in the zone table"

    print("OK: Backcourt shots are excluded from zones but still counted in totals.fga")


def test_both_frames_empty_returns_fallback() -> None:
    frames = {"Playoffs": _EMPTY_FRAMES, "Regular Season": _EMPTY_FRAMES}
    service = LeagueAnalyticsService()
    object.__setattr__(service, "_shot_chart_frames", lambda pid, season, season_type: frames[season_type])

    result = service.shot_chart(103, "2025-26")
    fallback = shot_chart_fallback()
    assert result["shots"] == fallback["shots"] == []
    assert result["zones"] == fallback["zones"] == []
    assert result["totals"] == fallback["totals"]
    assert result["truncated"] is False

    print("OK: an empty Playoffs and Regular Season frame returns the fallback shape without raising")


def test_truncation_caps_shots_but_not_totals() -> None:
    total_rows = _SHOT_CHART_MAX_POINTS + 250
    shots_rows = [
        _shot_row(i % 40, (i % 30) * 5, i % 2, "2PT Field Goal", "Mid-Range") for i in range(total_rows)
    ]
    league_rows = [{"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_ZONE_AREA": "Center(C)", "FGM": 100, "FGA": 300}]
    frames = {"Playoffs": _frames(shots_rows, league_rows), "Regular Season": _EMPTY_FRAMES}
    service = LeagueAnalyticsService()
    object.__setattr__(service, "_shot_chart_frames", lambda pid, season, season_type: frames[season_type])

    result = service.shot_chart(104, "2025-26")
    assert result["truncated"] is True
    assert len(result["shots"]) == _SHOT_CHART_MAX_POINTS, "shots list must be capped at _SHOT_CHART_MAX_POINTS"
    assert result["totals"]["fga"] == total_rows, "totals must reflect the full untruncated attempt count"

    print("OK: shot lists beyond _SHOT_CHART_MAX_POINTS are truncated without shrinking totals")


def main() -> None:
    test_zone_math_and_league_pooling()
    test_shot_type_mapping_and_totals()
    test_backcourt_excluded_but_counted_in_totals()
    test_both_frames_empty_returns_fallback()
    test_truncation_caps_shots_but_not_totals()
    print("OK: shot chart zone aggregation, fallback, and truncation all behave correctly")


if __name__ == "__main__":
    main()
