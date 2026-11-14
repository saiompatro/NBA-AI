"""Self-check for regular-season vs. playoff stat selection.

Run directly: python scripts/test_season_type.py
"""
from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path
from unittest import mock

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

from app.services import league_analytics
from app.services.league_analytics import LeagueAnalyticsService, active_season_type, current_season


def _teams_with_season_type(season_type: str) -> tuple[list[dict], list[str]]:
    """Run `playoff_teams` offline, returning its rows and every SeasonType requested."""
    requested: list[str] = []

    def fake_stats_frame(self, endpoint, params, result_name, timeout=None):
        requested.append(params.get("SeasonType", ""))
        if endpoint == "leaguedashteamstats" and params.get("MeasureType") == "Base" and "Location" not in params:
            return pd.DataFrame(
                [{"TEAM_ID": 1610612765, "W": 9, "L": 3, "PTS": 118.4, "PLUS_MINUS": 7.5, "FGA": 90, "FTA": 22}]
            )
        return pd.DataFrame()

    with mock.patch.object(league_analytics, "active_season_type", return_value=season_type), mock.patch.object(
        LeagueAnalyticsService, "_stats_frame", fake_stats_frame
    ), mock.patch.object(LeagueAnalyticsService, "_league_standings_frame", return_value={}), mock.patch.object(
        LeagueAnalyticsService, "_clutch_team_stats", return_value={}
    ), mock.patch.object(LeagueAnalyticsService, "_shot_zone_team_stats", return_value={}):
        rows = LeagueAnalyticsService().playoff_teams("2026-27", [])
    return rows, requested


def main() -> None:
    # Regular season: from the October rollover until the playoffs tip off.
    for day in (date(2026, 10, 20), date(2026, 11, 14), date(2027, 1, 1), date(2027, 4, 17)):
        assert active_season_type(day) == "Regular Season", day
    # Playoffs, then the offseason, where the just-finished playoffs stay the freshest data.
    for day in (date(2027, 4, 18), date(2027, 5, 30), date(2027, 6, 20), date(2027, 9, 30)):
        assert active_season_type(day) == "Playoffs", day
    # The season label and the season type must agree at the October rollover.
    assert current_season(date(2026, 9, 30)) == "2025-26" and active_season_type(date(2026, 9, 30)) == "Playoffs"
    assert current_season(date(2026, 10, 1)) == "2026-27" and active_season_type(date(2026, 10, 1)) == "Regular Season"

    rows, requested = _teams_with_season_type("Regular Season")
    assert requested and set(requested) == {"Regular Season"}, requested
    pistons = next(row for row in rows if row["abbr"] == "DET")
    assert pistons["net"] == 7.5, "real regular-season net rating must replace the seed-based estimate"
    assert pistons["pts"] == 118.4
    assert pistons["playoff_record"] == "0-0", "regular-season W/L must not be shown as a playoff record"
    # Regression: these fields were referenced but never computed, so every call raised.
    assert pistons["shot_profile"] and pistons["three_rate"] > 0 and pistons["efg_pct"] > 0

    rows, requested = _teams_with_season_type("Playoffs")
    assert set(requested) == {"Playoffs"}, requested
    pistons = next(row for row in rows if row["abbr"] == "DET")
    assert pistons["playoff_record"] == "9-3"

    print("season type OK")


if __name__ == "__main__":
    main()
