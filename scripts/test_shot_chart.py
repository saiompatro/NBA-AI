"""Self-check for NBALiveFeed live shot-chart tracking.

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.nba_live import NBALiveFeed
from app.services.shot_quality_service import ShotQualityService


class _FixedWinModel:
    def predict_home_win_probability(self, _features: dict) -> float:
        return 0.5


class _FixedShotModel:
    """Stands in for ShotQualityModel - constant prediction, no xgboost needed."""

    def predict(self, _context) -> float:
        return 0.42


def _feed() -> NBALiveFeed:
    return NBALiveFeed(
        shot_quality_service=ShotQualityService(_FixedShotModel()),
        win_model=_FixedWinModel(),
    )


# -- Fixtures ---------------------------------------------------------------

MADE_2PT = {
    "actionNumber": 2,
    "actionType": "2pt",
    "isFieldGoal": 1,
    "period": 1,
    "clock": "PT11M30.00S",
    "teamTricode": "BOS",
    "playerNameI": "J. Tatum",
    "shotDistance": 12.0,
    "x": 5.0,
    "y": 10.0,
    "shotResult": "Made",
    "description": "J. Tatum makes 12' Jump Shot",
}

REBOUND = {
    "actionNumber": 3,
    "actionType": "rebound",
    "isFieldGoal": 0,
    "period": 1,
    "clock": "PT11M25.00S",
    "teamTricode": "BOS",
    "description": "BOS Rebound",
}

MISSED_3PT_NO_RESULT = {
    "actionNumber": 4,
    "actionType": "3pt",
    "isFieldGoal": 1,
    "period": 1,
    "clock": "PT11M10.00S",
    "teamTricode": "MIA",
    "playerNameI": "J. Butler",
    "shotDistance": 24.0,
    "x": -15.0,
    "y": 20.0,
    "description": "J. Butler misses 24' 3PT Jump Shot",
}

NEW_MADE_3PT = {
    "actionNumber": 7,
    "actionType": "3pt",
    "isFieldGoal": 1,
    "period": 1,
    "clock": "PT09M40.00S",
    "teamTricode": "BOS",
    "playerNameI": "J. Tatum",
    "shotDistance": 26.0,
    "x": 20.0,
    "y": 18.0,
    "shotResult": "Made",
    "description": "J. Tatum makes 26' 3PT Jump Shot",
}


def test_scan_dedup_and_idle() -> None:
    feed = _feed()

    poll1 = [MADE_2PT, REBOUND, MISSED_3PT_NO_RESULT]
    chart = feed._update_shot_chart("game-1", poll1, period=1, clock="PT11M30.00S", score_diff=2)
    assert len(chart) == 2, f"expected 2 field-goal attempts, got {len(chart)}"
    assert [s["result"] for s in chart] == ["made", "missed"], chart

    # Entry contract on the first (made) shot.
    first = chart[0]
    assert first["shot_quality"] == 0.42, first
    assert isinstance(first["distance"], float) and first["distance"] == 12.0, first
    assert -55.0 <= first["angle"] <= 55.0, first
    assert first["team"] == "BOS", first
    assert first["player"] == "J. Tatum", first
    assert first["shot_value"] == 2, first
    assert first["action_number"] == "2", first

    # Repeat poll (same three actions) plus one new made 3pt -> dedup, length 3.
    poll2 = [MADE_2PT, REBOUND, MISSED_3PT_NO_RESULT, NEW_MADE_3PT]
    chart = feed._update_shot_chart("game-1", poll2, period=1, clock="PT09M40.00S", score_diff=2)
    assert len(chart) == 3, f"expected dedup to length 3, got {len(chart)}"
    assert [s["action_number"] for s in chart] == ["2", "4", "7"], chart
    assert chart[-1]["shot_value"] == 3, chart[-1]

    # Idle poll with the identical action list -> length unchanged.
    chart = feed._update_shot_chart("game-1", poll2, period=1, clock="PT09M40.00S", score_diff=2)
    assert len(chart) == 3, f"idle poll should not grow the chart, got {len(chart)}"

    return feed


def test_shot_result_precedence() -> None:
    # shotResult wins even when the description contradicts it.
    action = {
        "actionNumber": 10,
        "actionType": "2pt",
        "isFieldGoal": 1,
        "period": 2,
        "clock": "PT08M00.00S",
        "teamTricode": "MIA",
        "shotDistance": 8.0,
        "x": 3.0,
        "y": 8.0,
        "shotResult": "Missed",
        "description": "J. Butler makes 8' driving layup",
    }
    feed = _feed()
    chart = feed._update_shot_chart("game-x", [action], period=2, clock="PT08M00.00S", score_diff=0)
    assert len(chart) == 1, chart
    assert chart[0]["result"] == "missed", chart[0]


def test_unknown_outcome_is_recorded() -> None:
    action = {
        "actionNumber": 1,
        "actionType": "2pt",
        "isFieldGoal": 1,
        "period": 1,
        "clock": "PT06M00.00S",
        "shotDistance": 15.0,
        "x": 5.0,
        "y": 12.0,
        "description": "J. Doe shot attempt",
    }
    feed = _feed()
    chart = feed._update_shot_chart("game-x", [action], period=1, clock="PT06M00.00S", score_diff=0)
    assert len(chart) == 1, "an unclassifiable outcome must still be recorded"
    assert chart[0]["result"] == "unknown", chart[0]


def test_action_type_without_is_field_goal_key() -> None:
    three_no_flag = {
        "actionNumber": 1,
        "actionType": "3pt",
        "period": 1,
        "clock": "PT07M00.00S",
        "shotDistance": 25.0,
        "x": 22.0,
        "y": 15.0,
        "shotResult": "Made",
        "description": "made corner three",
    }
    free_throw = {
        "actionNumber": 2,
        "actionType": "freethrow",
        "isFieldGoal": 0,
        "period": 1,
        "clock": "PT06M55.00S",
        "description": "free throw made",
    }
    feed = _feed()
    chart = feed._update_shot_chart(
        "game-x", [three_no_flag, free_throw], period=1, clock="PT07M00.00S", score_diff=0
    )
    assert len(chart) == 1, "actionType alone should qualify a shot; free throws must be excluded"
    assert chart[0]["action_number"] == "1", chart[0]


def test_missing_location_is_skipped_but_not_poisoned() -> None:
    unlocated = {
        "actionNumber": 5,
        "actionType": "2pt",
        "isFieldGoal": 1,
        "period": 1,
        "clock": "PT05M00.00S",
        "shotResult": "Made",
        "description": "made shot, no coordinates yet",
    }
    feed = _feed()
    chart = feed._update_shot_chart("game-x", [unlocated], period=1, clock="PT05M00.00S", score_diff=0)
    assert chart == [], "a field goal without any location must not be plotted"

    located = dict(unlocated, shotDistance=10.0)
    chart = feed._update_shot_chart("game-x", [located], period=1, clock="PT05M00.00S", score_diff=0)
    assert len(chart) == 1, "the same action must be picked up once coordinates arrive"


def test_empty_actions_list() -> None:
    feed = _feed()
    chart = feed._update_shot_chart("game-x", [], period=1, clock="PT12M00.00S", score_diff=0)
    assert chart == [], "empty actions list must yield an empty chart, not raise"


def test_reset_on_game_id_change(feed_with_history: NBALiveFeed) -> None:
    reused_action_number = dict(MADE_2PT)  # actionNumber 2, already "seen" in game-1
    chart = feed_with_history._update_shot_chart(
        "game-2", [reused_action_number], period=1, clock="PT12M00.00S", score_diff=0
    )
    assert len(chart) == 1, "switching game_id must reset both the list and the seen-set"


def test_no_shot_quality_service() -> None:
    feed = NBALiveFeed(shot_quality_service=None, win_model=_FixedWinModel())
    chart = feed._update_shot_chart("game-x", [MADE_2PT], period=1, clock="PT11M30.00S", score_diff=0)
    assert chart == [], "with no shot-quality service the chart must stay empty, and never raise"


def main() -> None:
    feed_with_history = test_scan_dedup_and_idle()
    test_shot_result_precedence()
    test_unknown_outcome_is_recorded()
    test_action_type_without_is_field_goal_key()
    test_missing_location_is_skipped_but_not_poisoned()
    test_empty_actions_list()
    test_reset_on_game_id_change(feed_with_history)
    test_no_shot_quality_service()

    print(
        "OK: shot chart scans/filters field-goal actions, dedupes across polls, "
        "resets per game, honors shotResult precedence, records unknown outcomes, "
        "withholds unlocated shots without poisoning the seen-set, and stays empty "
        "with no shot-quality service"
    )


if __name__ == "__main__":
    main()
