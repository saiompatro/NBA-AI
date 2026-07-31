"""Self-check for NBALiveFeed win-probability trend tracking.

Run directly: python scripts/test_win_probability_history.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.nba_live import NBALiveFeed, _WP_HISTORY_MAX


class _FixedWinModel:
    def predict_home_win_probability(self, _features: dict) -> float:
        return 0.5


def _snapshot(feed: NBALiveFeed, game_id: str):
    return feed._build_snapshot(
        game_id=game_id,
        home_team="BOS",
        away_team="MIA",
        home_team_id="1",
        away_team_id="2",
        home_score=10,
        away_score=8,
        period=1,
        clock="PT10M00.00S",
        possession="BOS",
        home_fouls=0,
        away_fouls=0,
        shot_quality_model={"shot_quality": 0.5, "action_description": "test"},
        actions=[],
        source="test",
    )


def main() -> None:
    feed = NBALiveFeed(shot_quality_service=None, win_model=_FixedWinModel())

    for _ in range(5):
        snap = _snapshot(feed, "game-1")
    assert snap.win_probability_history == [0.5] * 5, "history should accumulate per snapshot"

    snap = _snapshot(feed, "game-2")
    assert snap.win_probability_history == [0.5], "history must reset when the tracked game changes"

    for _ in range(_WP_HISTORY_MAX + 50):
        snap = _snapshot(feed, "game-2")
    assert len(snap.win_probability_history) == _WP_HISTORY_MAX, "history must be capped"

    print("OK: win-probability history accumulates, resets per game, and is capped")


if __name__ == "__main__":
    main()
