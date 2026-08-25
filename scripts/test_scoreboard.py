"""Self-check for ESPN scoreboard event normalization (feeds /api/scoreboard).

Run directly: python scripts/test_scoreboard.py
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

from datetime import date

from app.services.league_analytics import LeagueAnalyticsService, normalize_scoreboard_event


def _competitor(home_away: str, abbr: str, name: str, score: str, record: str, winner: bool) -> dict:
    return {
        "homeAway": home_away,
        "winner": winner,
        "score": score,
        "team": {
            "abbreviation": abbr,
            "displayName": name,
            "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr.lower()}.png",
        },
        "records": [{"name": "overall", "type": "total", "summary": record}],
    }


def _event(state: str, detail: str) -> dict:
    return {
        "id": "401585183",
        "date": "2026-03-01T00:00Z",
        "shortName": "BOS @ NYK",
        "status": {"type": {"state": state, "detail": detail, "shortDetail": detail}},
        "competitions": [
            {
                "competitors": [
                    _competitor("away", "BOS", "Boston Celtics", "112" if state != "pre" else "0", "41-24", state == "post"),
                    _competitor("home", "NYK", "New York Knicks", "104" if state != "pre" else "0", "38-27", False),
                ]
            }
        ],
    }


def main() -> None:
    # Final game: correct shape, winner flagged, scores parsed as ints.
    final_game = normalize_scoreboard_event(_event("post", "Final"))
    assert final_game is not None
    assert final_game["status"] == "post"
    assert final_game["status_detail"] == "Final"
    assert final_game["matchup"] == "BOS @ NYK"
    assert final_game["away"]["abbr"] == "BOS"
    assert final_game["away"]["score"] == 112
    assert final_game["away"]["record"] == "41-24"
    assert final_game["away"]["winner"] is True
    assert final_game["home"]["abbr"] == "NYK"
    assert final_game["home"]["score"] == 104
    assert final_game["home"]["winner"] is False
    assert final_game["home"]["logo"].startswith("https://")

    # Scheduled (pre-tip) game: still normalizes, no winner.
    scheduled_game = normalize_scoreboard_event(_event("pre", "7:30 PM ET"))
    assert scheduled_game is not None
    assert scheduled_game["status"] == "pre"
    assert scheduled_game["away"]["winner"] is False

    # Live game.
    live_game = normalize_scoreboard_event(_event("in", "Q3 5:45"))
    assert live_game is not None
    assert live_game["status"] == "in"
    assert live_game["status_detail"] == "Q3 5:45"

    # Malformed event (no competitions) -> None, not a fabricated placeholder.
    assert normalize_scoreboard_event({}) is None
    assert normalize_scoreboard_event({"competitions": []}) is None
    assert normalize_scoreboard_event({"competitions": [{"competitors": []}]}) is None

    # A day with no NBA games must yield [] from the service, not fabricated rows.
    service = LeagueAnalyticsService()
    object.__setattr__(service, "_espn_scoreboard", lambda game_date: [])
    assert service.scoreboard_for_date(date(2026, 7, 4)) == []

    # A day with games flows the normalized event through unchanged in shape.
    object.__setattr__(service, "_espn_scoreboard", lambda game_date: [_event("post", "Final")])
    games = service.scoreboard_for_date(date(2026, 3, 1))
    assert len(games) == 1
    assert games[0]["matchup"] == "BOS @ NYK"

    print("OK: scoreboard event normalization produces the expected shape for pre/in/post games and empty input")


if __name__ == "__main__":
    main()
