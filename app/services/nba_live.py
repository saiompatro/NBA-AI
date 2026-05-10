from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.win_probability import WinProbabilityModel
from app.services.shot_quality_service import ShotQualityService


@dataclass
class GameSnapshot:
    is_live: bool
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    period: int
    clock: str
    time_remaining: int
    possession: str
    home_fouls: int
    away_fouls: int
    score_diff: int
    shot_quality_model: dict[str, Any]
    shot_quality: float
    home_win_probability: float
    away_win_probability: float
    events: list[str]
    source: str
    updated_at: str


@dataclass
class NoLiveSnapshot:
    is_live: bool
    message: str
    source: str
    updated_at: str


def _clock_to_seconds(clock: str) -> int:
    if not clock:
        return 0
    clean = clock.replace("PT", "").replace("M", ":").replace("S", "")
    try:
        minutes, seconds = clean.split(":")
        return int(minutes) * 60 + int(float(seconds))
    except ValueError:
        return 0


def _time_remaining(period: int, clock: str) -> int:
    regulation_total = 48 * 60
    elapsed_before_period = min(max(period - 1, 0), 4) * 12 * 60
    remaining_in_period = _clock_to_seconds(clock)
    if period <= 4:
        return max(regulation_total - elapsed_before_period - (12 * 60 - remaining_in_period), 0)
    return max(remaining_in_period, 0)


class NBALiveFeed:
    def __init__(self, shot_quality_service: ShotQualityService, win_model: WinProbabilityModel) -> None:
        self.shot_quality_service = shot_quality_service
        self.win_model = win_model

    def snapshot(self) -> GameSnapshot | NoLiveSnapshot:
        live = self._try_live_snapshot()
        if live:
            return live
        return NoLiveSnapshot(
            is_live=False,
            message="No NBA game is currently live. Showing analytics dashboards.",
            source="nba_api live scoreboard",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _try_live_snapshot(self) -> GameSnapshot | None:
        try:
            from nba_api.live.nba.endpoints import playbyplay, scoreboard

            board = scoreboard.ScoreBoard(timeout=4)
            games = board.get_dict().get("scoreboard", {}).get("games", [])
            active = [game for game in games if int(game.get("gameStatus") or 1) == 2]
            if not active:
                return None

            game = active[0]
            home = game["homeTeam"]
            away = game["awayTeam"]
            home_team = home.get("teamTricode", "HOME")
            away_team = away.get("teamTricode", "AWAY")
            home_score = int(home.get("score", 0) or 0)
            away_score = int(away.get("score", 0) or 0)
            period = int(game.get("period", 1) or 1)
            clock = game.get("gameClock") or "PT12M00.00S"
            game_id = game.get("gameId", "live")
            actions = playbyplay.PlayByPlay(game_id=game_id, timeout=4).get_dict().get("game", {}).get("actions", [])
            possession = self._possession(actions, home, away)
            score_diff = home_score - away_score
            remaining = _time_remaining(period, clock)
            shot_quality = self.shot_quality_service.from_live_actions(actions, period, remaining, score_diff)
            return self._build_snapshot(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                period=period,
                clock=clock,
                possession=possession,
                home_fouls=int(home.get("fouls", 0) or 0),
                away_fouls=int(away.get("fouls", 0) or 0),
                shot_quality_model=shot_quality.as_dict(),
                source="nba_api live scoreboard + play-by-play",
            )
        except Exception:
            return None

    def _build_snapshot(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        period: int,
        clock: str,
        possession: str,
        home_fouls: int,
        away_fouls: int,
        shot_quality_model: dict[str, Any],
        source: str,
    ) -> GameSnapshot:
        score_diff = home_score - away_score
        shot_quality = float(shot_quality_model["shot_quality"])
        home_probability = self.win_model.predict_home_win_probability(
            {
                "score_diff": score_diff,
                "time_remaining": _time_remaining(period, clock),
                "home_possession": 1.0 if possession == home_team else 0.0,
                "home_fouls": home_fouls,
                "away_fouls": away_fouls,
                "shot_quality": shot_quality,
            }
        )
        return GameSnapshot(
            is_live=True,
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            period=period,
            clock=clock,
            time_remaining=_time_remaining(period, clock),
            possession=possession,
            home_fouls=home_fouls,
            away_fouls=away_fouls,
            score_diff=score_diff,
            shot_quality_model=shot_quality_model,
            shot_quality=shot_quality,
            home_win_probability=home_probability,
            away_win_probability=round(1 - home_probability, 4),
            events=[
                shot_quality_model["action_description"],
                f"{possession} possession with {shot_quality * 100:.1f}% model shot quality",
                f"Score differential: {score_diff:+d}",
                f"Model source: {source}",
            ],
            source=source,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _possession(actions: list[dict[str, Any]], home: dict[str, Any], away: dict[str, Any]) -> str:
        home_id = home.get("teamId")
        away_id = away.get("teamId")
        home_code = home.get("teamTricode", "HOME")
        away_code = away.get("teamTricode", "AWAY")
        for action in reversed(actions):
            possession = action.get("possession")
            if possession == home_id:
                return home_code
            if possession == away_id:
                return away_code
            tricode = action.get("teamTricode")
            if tricode in {home_code, away_code}:
                return tricode
        return home_code

    @staticmethod
    def serialize(snapshot: GameSnapshot | NoLiveSnapshot) -> dict[str, Any]:
        return asdict(snapshot)
