"""Season-phase check: stat queries must follow the live part of the NBA calendar.

Run with:  python scripts/test_season_phase.py   (or pytest scripts/test_season_phase.py)
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import league_analytics  # noqa: E402
from app.services.league_analytics import (  # noqa: E402
    LeagueAnalyticsService,
    _season_type_order,
    current_season,
    current_season_type,
)


def test_regular_season_window() -> None:
    for day in (date(2026, 10, 20), date(2026, 11, 11), date(2027, 1, 15), date(2027, 3, 31), date(2027, 4, 17)):
        assert current_season_type(day) == "Regular Season", day
    assert current_season(date(2026, 11, 11)) == "2026-27"


def test_playoffs_and_offseason_window() -> None:
    # Off-season keeps pointing at the playoffs of the season current_season() still names.
    for day in (date(2027, 4, 18), date(2027, 5, 20), date(2027, 6, 10), date(2027, 8, 1), date(2027, 9, 30)):
        assert current_season_type(day) == "Playoffs", day
    assert current_season(date(2027, 8, 1)) == "2026-27"


def test_fallback_order_is_the_other_type() -> None:
    assert _season_type_order(date(2026, 11, 11)) == ("Regular Season", "Playoffs")
    assert _season_type_order(date(2027, 5, 20)) == ("Playoffs", "Regular Season")


def test_team_stats_query_uses_live_season_type() -> None:
    seen: list[str] = []

    def fake_stats_frame(self, endpoint, params, result_set):  # noqa: ANN001
        seen.append(str(params.get("SeasonType")))
        return pd.DataFrame()

    original_frame = LeagueAnalyticsService._stats_frame
    original_type = league_analytics.current_season_type
    try:
        LeagueAnalyticsService._stats_frame = fake_stats_frame  # type: ignore[method-assign]
        league_analytics.current_season_type = lambda today=None: "Regular Season"
        LeagueAnalyticsService()._advanced_team_stats("2026-27")
        league_analytics.current_season_type = lambda today=None: "Playoffs"
        LeagueAnalyticsService()._advanced_team_stats("2025-26")
    finally:
        LeagueAnalyticsService._stats_frame = original_frame  # type: ignore[method-assign]
        league_analytics.current_season_type = original_type
    assert seen == ["Regular Season", "Playoffs"], seen


if __name__ == "__main__":
    test_regular_season_window()
    test_playoffs_and_offseason_window()
    test_fallback_order_is_the_other_type()
    test_team_stats_query_uses_live_season_type()
    print("season phase checks passed")
