"""Self-check for NBA CDN boxscore parsing.

Run directly: python scripts/test_box_score.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Stub the `app` package (and the torch-backed win_probability module) so importing
# nba_live doesn't drag in app/__init__.py -> app.main -> torch, which isn't needed
# for this check and isn't always loadable in every environment.
_app_stub = types.ModuleType("app")
_app_stub.__path__ = [str(_ROOT / "app")]
sys.modules["app"] = _app_stub

_win_prob_stub = types.ModuleType("app.models.win_probability")
_win_prob_stub.WinProbabilityModel = object
sys.modules["app.models.win_probability"] = _win_prob_stub

from app.services.nba_live import _box_score_minutes, _parse_boxscore


def _player(name: str, minutes: str, points: int) -> dict:
    return {
        "name": name,
        "position": "G",
        "statistics": {
            "minutes": minutes,
            "points": points,
            "reboundsTotal": 3,
            "assists": 2,
            "steals": 1,
            "blocks": 0,
            "plusMinusPoints": 5,
        },
    }


def main() -> None:
    assert _box_score_minutes("PT25M30.00S") == "25:30"
    assert _box_score_minutes("") == "0:00"
    assert _box_score_minutes("garbage") == "0:00"

    data = {
        "game": {
            "homeTeam": {
                "players": [
                    _player("Bench Guy", "", 0),  # hasn't checked in -> excluded
                    _player("Low Scorer", "PT10M00.00S", 4),
                    _player("Top Scorer", "PT30M00.00S", 28),
                    _player("Mid Scorer", "PT20M00.00S", 15),
                ]
            },
            "awayTeam": {"players": [_player("Only Player", "PT12M00.00S", 9)]},
        }
    }

    box = _parse_boxscore(data, top_n=2)
    assert [p["name"] for p in box["home"]] == ["Top Scorer", "Mid Scorer"], "must sort by points desc and cap at top_n"
    assert box["home"][0]["minutes"] == "30:00"
    assert [p["name"] for p in box["away"]] == ["Only Player"]

    print("OK: boxscore minutes formatting and per-team top-scorer reduction work correctly")


if __name__ == "__main__":
    main()
