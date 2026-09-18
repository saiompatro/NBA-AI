"""Self-check for current-roster reconciliation after offseason moves.

Run directly: python scripts/test_roster_sync.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import LeagueAnalyticsService, player_name_key


def _roster_player(name: str, team: str, team_name: str, player_id: int) -> dict:
    return {
        "id": player_id,
        "slug": player_name_key(name).replace(" ", "-"),
        "player": name,
        "team": team,
        "team_name": team_name,
        "team_id": 1610612761,
        "team_slug": "toronto-raptors",
        "role": "Bench",
        "rotation_rank": 9,
        "headshot": "",
        "gp": 0,
        "min": 8.0,
        "pts": 3.0,
        "reb": 1.0,
        "ast": 1.0,
        "stl": 0.1,
        "blk": 0.1,
        "fg_pct": 40.0,
        "fg3_pct": 30.0,
        "ft_pct": 70.0,
        "plus_minus": 0.0,
        "impact": 5.0,
        "ts_pct": 50.0,
        "usg_pct": 10.0,
        "pie": 5.0,
        "trend": [],
        "sentiment": {},
        "roster_source": "ESPN current team roster",
        "stats_source": "estimated (no prior playoff row)",
    }


class FakeAnalytics(LeagueAnalyticsService):
    def _espn_rotation_players(self, news: list[dict]) -> list[dict]:
        return [
            _roster_player("Traded Stár", "TOR", "Toronto Raptors", 1),
            _roster_player("New Rookie", "TOR", "Toronto Raptors", 2),
        ]

    def _stats_frame(self, endpoint: str, params: dict, result_name: str, timeout=None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "PLAYER_ID": 101,
                    "PLAYER_NAME": "Traded Star",
                    "TEAM_ID": 1610612738,
                    "PTS": 24.0,
                    "REB": 7.0,
                    "AST": 5.0,
                    "STL": 1.0,
                    "BLK": 0.5,
                    "PLUS_MINUS": 4.0,
                    "FG_PCT": 0.49,
                    "FG3_PCT": 0.38,
                    "FT_PCT": 0.85,
                    "GP": 12,
                    "MIN": 35.0,
                    "TOV": 2.0,
                },
                {
                    "PLAYER_ID": 102,
                    "PLAYER_NAME": "Departed Player",
                    "TEAM_ID": 1610612761,
                    "PTS": 18.0,
                    "REB": 4.0,
                    "AST": 3.0,
                    "STL": 0.5,
                    "BLK": 0.2,
                    "PLUS_MINUS": 1.0,
                    "FG_PCT": 0.45,
                    "FG3_PCT": 0.34,
                    "FT_PCT": 0.80,
                    "GP": 10,
                    "MIN": 30.0,
                    "TOV": 2.0,
                },
            ]
        )

    def _advanced_player_stats(self, season: str) -> dict[int, dict]:
        return {}


def main() -> None:
    players = FakeAnalytics().playoff_players("2025-26", [])
    by_name = {player["player"]: player for player in players}

    assert "Departed Player" not in by_name, "historical stats must not resurrect a departed player"
    assert by_name["Traded Stár"]["team"] == "TOR", "current roster must win over the historical team"
    assert by_name["Traded Stár"]["pts"] == 24.0, "historical performance should still be retained"
    assert by_name["Traded Stár"]["id"] == 101, "NBA id should replace a roster fallback id"
    assert by_name["New Rookie"]["stats_source"].startswith("estimated"), "new arrivals must remain visible"
    assert by_name["Traded Stár"]["rotation_rank"] == 1, "real minutes should set the rotation order"
    assert player_name_key("Luka Dončić") == player_name_key("Luka Doncic"), "accent variants must join"

    print("OK: current rosters override old teams while preserving prior playoff stats")


if __name__ == "__main__":
    main()
