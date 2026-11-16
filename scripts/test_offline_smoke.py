"""Offline smoke test: every dashboard endpoint must still answer when no data source is reachable.

A merge once dropped a few definitions (`efg_pct`/`shot_profile`/`three_rate` in
`playoff_teams`, `_SHOT_CHART_MAX_POINTS`, and the `date`/`datetime` imports in
app/main.py). Nothing failed at import time, but the teams, analytics,
prediction, power-ranking and scoreboard endpoints raised NameError on every
request. The unit tests only cover pure helpers, so this walks the real code
paths with the network cut off (fallback data) and with a canned stats frame.

Run with:  python scripts/test_offline_smoke.py   (or pytest scripts/test_offline_smoke.py)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import league_analytics  # noqa: E402
from app.services.league_analytics import (  # noqa: E402
    PLAYOFF_SEEDS_2026,
    TRACKED_TEAMS,
    LeagueAnalyticsService,
    current_season,
)


def _no_network(*_args, **_kwargs):
    raise requests.ConnectionError("network disabled for the offline smoke test")


def _offline():
    return mock.patch.object(requests.sessions.Session, "request", _no_network)


def test_teams_and_rankings_render_from_fallbacks() -> None:
    with _offline():
        service = LeagueAnalyticsService()
        teams = service.playoff_teams(current_season(), [])
        rankings = service.power_rankings(current_season(), [])
    assert len(teams) == len(TRACKED_TEAMS) == 30
    for team in teams:
        assert isinstance(team["efg_pct"], float)
        zones = team["shot_profile"]
        assert len(zones) == 5, zones
        assert abs(sum(zone["freq"] for zone in zones) - 100.0) < 0.6, zones
        threes = sum(zone["freq"] for zone in zones if zone["key"] in ("corner3", "atb3"))
        assert abs(team["three_rate"] - threes) < 0.11
    assert [row["rank"] for row in rankings] == list(range(1, len(teams) + 1))


def test_team_rows_use_real_shot_zones_when_available() -> None:
    zone_row = {"TEAM_ID": PLAYOFF_SEEDS_2026[0]["team_id"], "TEAM_NAME": PLAYOFF_SEEDS_2026[0]["team"]}
    attempts = {"RESTRICTED_AREA": (300, 200), "IN_THE_PAINT_(NON_RA)": (100, 40), "MID_RANGE": (100, 40),
                "LEFT_CORNER_3": (50, 20), "RIGHT_CORNER_3": (50, 20), "ABOVE_THE_BREAK_3": (400, 140)}
    for zone in league_analytics.SHOT_ZONES:
        prefix = league_analytics._zone_column_key(zone["api_name"])
        fga, fgm = next(v for k, v in attempts.items() if league_analytics._zone_column_key(k) == prefix)
        zone_row[f"{prefix}_FGA"], zone_row[f"{prefix}_FGM"] = fga, fgm
    # Equal service instances share the lru_cache, so drop what the offline run cached.
    LeagueAnalyticsService._shot_zone_team_stats.cache_clear()
    try:
        with _offline(), mock.patch.object(
            LeagueAnalyticsService, "_shot_location_frame", lambda self, season: pd.DataFrame([zone_row])
        ):
            teams = LeagueAnalyticsService().playoff_teams(current_season(), [])
    finally:
        LeagueAnalyticsService._shot_zone_team_stats.cache_clear()
    first = next(team for team in teams if team["team_id"] == zone_row["TEAM_ID"])
    assert first["three_rate"] == 50.0, first["shot_profile"]
    rim = next(zone for zone in first["shot_profile"] if zone["key"] == "rim")
    assert rim["freq"] == 30.0 and rim["fg_pct"] == 66.7, rim


def test_shot_chart_caps_raw_points() -> None:
    cap = league_analytics._SHOT_CHART_MAX_POINTS
    shots = pd.DataFrame(
        {
            "PLAYER_NAME": ["Test Player"] * (cap + 25),
            "LOC_X": 0, "LOC_Y": 10, "SHOT_MADE_FLAG": 1,
            "SHOT_TYPE": "2PT Field Goal", "SHOT_ZONE_BASIC": "Restricted Area",
        }
    )
    with _offline(), mock.patch.object(
        LeagueAnalyticsService,
        "_shot_chart_frames",
        lambda self, player_id, season, season_type: {"Shot_Chart_Detail": shots, "LeagueAverages": pd.DataFrame()},
    ):
        chart = LeagueAnalyticsService().shot_chart(1, current_season())
    assert len(chart["shots"]) == cap, len(chart["shots"])


def test_every_api_route_answers_offline() -> None:
    from app.main import create_app

    away, home = PLAYOFF_SEEDS_2026[1]["abbr"], PLAYOFF_SEEDS_2026[0]["abbr"]
    routes = [
        "/api/analytics", "/api/table", "/api/players", "/api/teams", "/api/standings", "/api/schedule",
        "/api/scoreboard", "/api/scoreboard?date=2026-11-12", "/api/scoreboard?date=not-a-date",
        "/api/power-rankings", "/api/model-performance", f"/api/game-prediction?away={away}&home={home}",
        f"/api/head-to-head?away={away}&home={home}", "/api/players/2544/game-log", "/api/players/2544/shot-chart",
        "/api/shot-quality", "/api/injuries", "/api/injuries?team=BOS", "/",
    ]
    with _offline():
        client = create_app().test_client()
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200, f"{route} -> {response.status_code}"
        prediction = client.get(f"/api/game-prediction?away={away}&home={home}").get_json()
        assert prediction["ok"] is True, prediction
        assert client.get("/api/scoreboard?date=2026-11-12").get_json()["date"] == "2026-11-12"


if __name__ == "__main__":
    test_teams_and_rankings_render_from_fallbacks()
    test_team_rows_use_real_shot_zones_when_available()
    test_shot_chart_caps_raw_points()
    test_every_api_route_answers_offline()
    print("OK: teams, rankings, shot chart and every API route answer with all data sources offline")
