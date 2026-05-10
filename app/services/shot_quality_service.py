from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Any

from app.models.shot_quality import ShotContext, ShotQualityModel


@dataclass(frozen=True)
class ShotQualityResult:
    context: ShotContext
    shot_quality: float
    source: str
    action_description: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "context": {
                "distance": self.context.distance,
                "angle": self.context.angle,
                "defender_distance": self.context.defender_distance,
                "shot_clock": self.context.shot_clock,
                "game_situation": self.context.game_situation,
            },
            "shot_quality": self.shot_quality,
            "source": self.source,
            "action_description": self.action_description,
        }


class ShotQualityService:
    """Linked shot-quality model fed by NBA data, not user-entered controls."""

    def __init__(self, model: ShotQualityModel) -> None:
        self.model = model

    def from_live_actions(
        self,
        actions: list[dict[str, Any]],
        period: int,
        time_remaining: int,
        score_diff: int,
    ) -> ShotQualityResult:
        shot_action = self._latest_field_goal_action(actions)
        if shot_action:
            context = self._context_from_action(shot_action, period, time_remaining, score_diff)
            return ShotQualityResult(
                context=context,
                shot_quality=self.model.predict(context),
                source="nba_api live play-by-play",
                action_description=shot_action.get("description") or "Latest field goal action",
            )

        return self.from_game_state(period, time_remaining, score_diff)

    def from_game_state(self, period: int, time_remaining: int, score_diff: int) -> ShotQualityResult:
        game_situation = self._game_situation(period, time_remaining, score_diff)
        context = ShotContext(
            distance=18.0,
            angle=0.0,
            defender_distance=4.5,
            shot_clock=12.0,
            game_situation=game_situation,
        )
        return ShotQualityResult(
            context=context,
            shot_quality=self.model.predict(context),
            source="derived from game state",
            action_description="No shot-tracking action available yet",
        )

    def _context_from_action(
        self,
        action: dict[str, Any],
        period: int,
        time_remaining: int,
        score_diff: int,
    ) -> ShotContext:
        distance, angle = self._court_location(action)
        defender_distance = self._first_numeric(
            action,
            [
                "defenderDistance",
                "closestDefenderDistance",
                "closeDefDist",
                "defender_distance",
            ],
            default=4.5,
        )
        shot_clock = self._first_numeric(
            action,
            ["shotClock", "shotClockSeconds", "shot_clock"],
            default=self._estimated_shot_clock(action),
        )
        return ShotContext(
            distance=round(distance, 1),
            angle=round(angle, 1),
            defender_distance=round(defender_distance, 1),
            shot_clock=round(shot_clock, 1),
            game_situation=self._game_situation(period, time_remaining, score_diff),
        )

    @staticmethod
    def _latest_field_goal_action(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
        for action in reversed(actions):
            if action.get("isFieldGoal") == 1 or action.get("actionType") in {"2pt", "3pt"}:
                return action
        return None

    @staticmethod
    def _first_numeric(action: dict[str, Any], keys: list[str], default: float) -> float:
        for key in keys:
            value = action.get(key)
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return default

    def _court_location(self, action: dict[str, Any]) -> tuple[float, float]:
        if action.get("shotDistance") not in (None, ""):
            distance = float(action["shotDistance"])
        else:
            x = self._first_numeric(action, ["x", "xLegacy"], default=0.0)
            y = self._first_numeric(action, ["y", "yLegacy"], default=0.0)
            if abs(x) > 60 or abs(y) > 60:
                x /= 10
                y /= 10
            distance = min(hypot(x, y), 35.0)

        x_for_angle = self._first_numeric(action, ["x", "xLegacy"], default=0.0)
        y_for_angle = self._first_numeric(action, ["y", "yLegacy"], default=max(distance, 1.0))
        if abs(x_for_angle) > 60 or abs(y_for_angle) > 60:
            x_for_angle /= 10
            y_for_angle /= 10
        angle = degrees(atan2(x_for_angle, max(abs(y_for_angle), 0.1)))
        return distance, max(-55.0, min(55.0, angle))

    @staticmethod
    def _estimated_shot_clock(action: dict[str, Any]) -> float:
        action_number = int(action.get("actionNumber") or 0)
        return max(3.0, 24.0 - float(action_number % 24))

    @staticmethod
    def _game_situation(period: int, time_remaining: int, score_diff: int) -> int:
        if period >= 4 and time_remaining <= 300 and abs(score_diff) <= 8:
            return 3
        return min(max(period - 1, 0), 2)
