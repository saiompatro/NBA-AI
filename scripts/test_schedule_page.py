"""Self-check for the schedule-page ESPN event parser (used by the #/schedule view).

Run directly: python scripts/test_schedule_page.py
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

from app.services.league_analytics import _schedule_event_to_game, fallback_schedule


def _event(state: str, completed: bool, away_score: str = "0", home_score: str = "0") -> dict:
    return {
        "date": "2026-05-10T23:30Z",
        "shortName": "NYK @ BOS",
        "status": {"type": {"state": state, "completed": completed, "shortDetail": "7:30 PM ET"}},
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "away", "score": away_score, "team": {"abbreviation": "NYK"}},
                    {"homeAway": "home", "score": home_score, "team": {"abbreviation": "BOS"}},
                ]
            }
        ],
    }


def main() -> None:
    assert _schedule_event_to_game({"competitions": []}) is None, "an event with no competitions must be skipped"

    scheduled = _schedule_event_to_game(_event("pre", False))
    assert scheduled["away"] == "NYK" and scheduled["home"] == "BOS"
    assert scheduled["completed"] is False
    assert scheduled["away_score"] == 0 and scheduled["home_score"] == 0, "an unplayed game must not show a score"

    final = _schedule_event_to_game(_event("post", True, away_score="101", home_score="110"))
    assert final["completed"] is True, "a finished game must be flagged completed"
    assert final["away_score"] == 101 and final["home_score"] == 110, "final scores must be parsed as integers"

    fallback = fallback_schedule()
    assert fallback, "fallback_schedule must never be empty"
    dates = [day["date"] for day in fallback]
    assert dates == sorted(dates), "fallback days must be in chronological order"
    for day in fallback:
        assert isinstance(day["games"], list) and day["games"], "every fallback day must carry at least one game"

    print("OK: schedule events parse scores/completion correctly and the fallback schedule is well-formed")


if __name__ == "__main__":
    main()
