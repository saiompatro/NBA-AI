"""Self-check for the date-navigable scores feed (`/api/scores`).

Run directly: python scripts/test_scores.py
"""
from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Stub the `app` package so importing league_analytics doesn't drag in
# app/__init__.py -> app.main -> flask/torch, which this check doesn't need.
_app_stub = types.ModuleType("app")
_app_stub.__path__ = [str(_ROOT / "app")]
sys.modules["app"] = _app_stub

from app.services.league_analytics import LeagueAnalyticsService, normalize_team_abbr


def _event(away_abbr: str, home_abbr: str, away_score, home_score, state: str, winner: str | None = None) -> dict:
    def _competitor(abbr: str, score, is_winner: bool) -> dict:
        return {
            "homeAway": "home" if abbr == home_abbr else "away",
            "team": {"abbreviation": abbr, "shortDisplayName": abbr, "logo": f"https://logos/{abbr}.png"},
            "score": score,
            "winner": is_winner,
            "records": [{"summary": "10-5"}],
            "linescores": [{"value": 25}, {"value": 30}, {"value": 20}, {"value": 22}],
        }

    return {
        "id": "401000001",
        "date": "2026-01-15T00:00Z",
        "status": {"type": {"state": state, "shortDetail": "Final" if state == "post" else "7:00 PM ET"}},
        "competitions": [
            {
                "competitors": [
                    _competitor(away_abbr, away_score, winner == away_abbr),
                    _competitor(home_abbr, home_score, winner == home_abbr),
                ]
            }
        ],
    }


def main() -> None:
    # Newly-added ESPN abbreviation aliases resolve to this app's NBA Stats convention.
    assert normalize_team_abbr("GS") == "GSW"
    assert normalize_team_abbr("UTAH") == "UTA"
    assert normalize_team_abbr("NO") == "NOP"
    assert normalize_team_abbr("WSH") == "WAS"
    assert normalize_team_abbr("DET") == "DET"  # untouched abbreviations pass through

    service = LeagueAnalyticsService()
    events = [_event("GS", "DET", 97, 101, "post", winner="DET")]
    with patch.object(LeagueAnalyticsService, "_espn_scoreboard", return_value=events):
        games = service.scores_for_date(date(2026, 1, 15))

    assert len(games) == 1
    game = games[0]
    assert game["status_state"] == "post"
    assert game["away"]["abbr"] == "GSW", "ESPN's 'GS' must normalize to GSW"
    assert game["home"]["abbr"] == "DET"
    assert game["away"]["score"] == 97
    assert game["home"]["score"] == 101
    assert game["home"]["winner"] is True
    assert game["away"]["winner"] is False
    assert game["home"]["linescores"] == [25, 30, 20, 22]
    assert game["away"]["record"] == "10-5"

    # A day with no games back should produce an empty list, not an error.
    with patch.object(LeagueAnalyticsService, "_espn_scoreboard", return_value=[]):
        assert service.scores_for_date(date(2026, 7, 1)) == []

    # Today's scoreboard must bypass the process-lifetime cache used for past days,
    # so a live score actually updates across repeated calls in the same process.
    calls = {"cached": 0, "fresh": 0}

    def _fake_cached(_self, _day):
        calls["cached"] += 1
        return []

    def _fake_fresh(_self, _day):
        calls["fresh"] += 1
        return []

    with patch.object(LeagueAnalyticsService, "_espn_scoreboard_cached", _fake_cached), \
         patch.object(LeagueAnalyticsService, "_fetch_espn_scoreboard", _fake_fresh):
        service._espn_scoreboard(date.today())
        service._espn_scoreboard(date.today() - __import__("datetime").timedelta(days=1))

    assert calls["fresh"] == 1, "today's scoreboard must always hit the network, never the cache"
    assert calls["cached"] == 1, "a finished past day should go through the cached path"

    print("OK: scores_for_date parsing, team-alias normalization, and today-vs-past caching all work correctly")


if __name__ == "__main__":
    main()
