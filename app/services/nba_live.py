from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.win_probability import WinProbabilityModel
from app.services.injury_news_watch import InjuryNewsWatch
from app.services.player_status_tracker import track as track_player_status
from app.services.shot_quality_service import ShotQualityService


# How much each unit of (impact_delta_per_min * remaining_minutes) shifts logit(p).
# Tuned so a Wembanyama-level loss (~1.5 impact/min) at full game remaining
# (~48 min) produces ~12-15 pp drop in win probability.
K_IMPACT_SHIFT = 0.05

# Refresh player-impact table at most once every 6 hours.
_PLAYER_TABLE_TTL = 6 * 3600


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
    raw_home_win_probability: float
    home_win_probability: float
    away_win_probability: float
    impact_delta: float
    home_players_out: list[dict[str, Any]]
    away_players_out: list[dict[str, Any]]
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


def _logit(p: float) -> float:
    p = max(0.001, min(0.999, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class NBALiveFeed:
    def __init__(
        self,
        shot_quality_service: ShotQualityService,
        win_model: WinProbabilityModel,
        analytics_service: Any | None = None,
    ) -> None:
        self.shot_quality_service = shot_quality_service
        self.win_model = win_model
        self._analytics = analytics_service
        self._injury_watch = InjuryNewsWatch()

        # player_id (int) → {impact_per_min, avg_min, team_id, name}
        self._player_table: dict[int, dict[str, Any]] = {}
        self._player_table_loaded_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Live snapshot construction
    # ------------------------------------------------------------------

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
            home_team_id = str(home.get("teamId", ""))
            away_team_id = str(away.get("teamId", ""))

            actions = (
                playbyplay.PlayByPlay(game_id=game_id, timeout=4)
                .get_dict()
                .get("game", {})
                .get("actions", [])
            )
            possession = self._possession(actions, home, away)
            score_diff = home_score - away_score
            remaining = _time_remaining(period, clock)
            shot_quality = self.shot_quality_service.from_live_actions(actions, period, remaining, score_diff)

            # Refresh player table and injury news every ~60 s
            self._maybe_refresh_player_table()
            self._maybe_refresh_injury_news(home_team, away_team)

            return self._build_snapshot(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_score=home_score,
                away_score=away_score,
                period=period,
                clock=clock,
                possession=possession,
                home_fouls=int(home.get("fouls", 0) or 0),
                away_fouls=int(away.get("fouls", 0) or 0),
                shot_quality_model=shot_quality.as_dict(),
                actions=actions,
                source="nba_api live scoreboard + play-by-play",
            )
        except Exception:
            return None

    def _build_snapshot(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        home_team_id: str,
        away_team_id: str,
        home_score: int,
        away_score: int,
        period: int,
        clock: str,
        possession: str,
        home_fouls: int,
        away_fouls: int,
        shot_quality_model: dict[str, Any],
        actions: list[dict[str, Any]],
        source: str,
    ) -> GameSnapshot:
        score_diff = home_score - away_score
        shot_quality = float(shot_quality_model["shot_quality"])
        remaining = _time_remaining(period, clock)

        raw_probability = self.win_model.predict_home_win_probability(
            {
                "score_diff": score_diff,
                "time_remaining": remaining,
                "home_possession": 1.0 if possession == home_team else 0.0,
                "home_fouls": home_fouls,
                "away_fouls": away_fouls,
                "shot_quality": shot_quality,
            }
        )

        # Build rotation_minutes for long-absence detection
        rotation_minutes = {
            pid: int(info.get("avg_min", 0))
            for pid, info in self._player_table.items()
        }

        status = track_player_status(actions, home_team_id, away_team_id, rotation_minutes)
        home_players_out = status["home_out"]
        away_players_out = status["away_out"]

        # Compute impact-weighted probability adjustment
        home_impact_lost = self._impact_lost(home_players_out)
        away_impact_lost = self._impact_lost(away_players_out)
        impact_delta_per_min = away_impact_lost - home_impact_lost  # positive → good for home

        remaining_minutes = remaining / 60.0
        shift = K_IMPACT_SHIFT * impact_delta_per_min * remaining_minutes
        adjusted_probability = round(
            max(0.01, min(0.99, _sigmoid(_logit(raw_probability) + shift))),
            4,
        )

        events = self._build_events(
            shot_quality_model=shot_quality_model,
            possession=possession,
            shot_quality=shot_quality,
            score_diff=score_diff,
            source=source,
            home_players_out=home_players_out,
            away_players_out=away_players_out,
            raw_probability=raw_probability,
            adjusted_probability=adjusted_probability,
            home_team=home_team,
            away_team=away_team,
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
            time_remaining=remaining,
            possession=possession,
            home_fouls=home_fouls,
            away_fouls=away_fouls,
            score_diff=score_diff,
            shot_quality_model=shot_quality_model,
            shot_quality=shot_quality,
            raw_home_win_probability=raw_probability,
            home_win_probability=adjusted_probability,
            away_win_probability=round(1 - adjusted_probability, 4),
            impact_delta=round(impact_delta_per_min, 3),
            home_players_out=home_players_out,
            away_players_out=away_players_out,
            events=events,
            source=source,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Impact helpers
    # ------------------------------------------------------------------

    def _impact_lost(self, players_out: list[dict[str, Any]]) -> float:
        total = 0.0
        for player in players_out:
            pid_raw = player.get("player_id", "")
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            entry = self._player_table.get(pid)
            if entry:
                total += entry.get("impact_per_min", 0.0)
        return total

    def _maybe_refresh_player_table(self) -> None:
        if not self._analytics:
            return
        now = time.monotonic()
        if now - self._player_table_loaded_at < _PLAYER_TABLE_TTL and self._player_table:
            return
        try:
            from app.services.league_analytics import current_season
            season = current_season()
            players = self._analytics.playoff_players(season, [])
            table: dict[int, dict[str, Any]] = {}
            for p in players:
                pid = int(p.get("id") or 0)
                if not pid:
                    continue
                avg_min = float(p.get("min") or 1.0) or 1.0
                impact = float(p.get("impact") or 0.0)
                table[pid] = {
                    "name": p.get("player", ""),
                    "team": p.get("team", ""),
                    "avg_min": avg_min,
                    "impact_per_min": impact / avg_min,
                }
            self._player_table = table
            self._player_table_loaded_at = now
        except Exception:
            pass

    def _maybe_refresh_injury_news(self, home_team: str, away_team: str) -> None:
        player_names = [
            info["name"]
            for info in self._player_table.values()
            if info.get("team") in {home_team, away_team}
        ]
        try:
            import time as _time
            refresh_key = str(int(_time.time() // 60))
            self._injury_watch.refresh(
                team_terms=[home_team, away_team],
                player_terms=player_names[:10],
                refresh_key=refresh_key,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Events list
    # ------------------------------------------------------------------

    def _build_events(
        self,
        shot_quality_model: dict[str, Any],
        possession: str,
        shot_quality: float,
        score_diff: int,
        source: str,
        home_players_out: list[dict[str, Any]],
        away_players_out: list[dict[str, Any]],
        raw_probability: float,
        adjusted_probability: float,
        home_team: str,
        away_team: str,
    ) -> list[str]:
        events: list[str] = [
            shot_quality_model["action_description"],
            f"{possession} possession with {shot_quality * 100:.1f}% model shot quality",
            f"Score differential: {score_diff:+d}",
        ]

        # Ejection / foul-out / injury events
        all_out = [(p, home_team) for p in home_players_out] + [(p, away_team) for p in away_players_out]
        for player, team in all_out:
            name = player.get("name", "Unknown")
            reason = player.get("reason", "unavailable")
            q = player.get("period", "?")
            clock = player.get("clock", "")
            events.append(f"{name} ({team}) — {reason} [Q{q} {clock}]")

        # Probability adjustment annotation
        if abs(adjusted_probability - raw_probability) >= 0.005:
            direction = "+" if adjusted_probability > raw_probability else "-"
            delta_pp = abs(round((adjusted_probability - raw_probability) * 100, 1))
            events.append(
                f"Win prob adjusted {direction}{delta_pp}pp "
                f"({round(raw_probability * 100)}% model → {round(adjusted_probability * 100)}% adjusted)"
            )

        # News alerts
        for alert in self._injury_watch.alerts()[:3]:
            events.append(f"[News] {alert['headline']} ({alert['source']})")

        events.append(f"Model source: {source}")
        return events

    # ------------------------------------------------------------------
    # Possession detection
    # ------------------------------------------------------------------

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
