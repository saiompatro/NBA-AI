"""Fit the pre-game ("normal") predictor against real NBA game results.

The pre-game model predicts a game before tip-off with:

    expected_home_margin = (home_net - away_net) + home_court_advantage
    P(home win)          = sigmoid(expected_home_margin / scale)

This script downloads several seasons of *real* completed games plus each
team's net rating, then chooses the two free constants
(`home_court_advantage` and `scale`) that best match what actually happened
(lowest log-loss). The result is written to data/pregame_calibration.json,
which app/services/league_analytics.py loads at prediction time.

Run it with:  python scripts/calibrate_pregame.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.league_analytics import (  # noqa: E402
    LeagueAnalyticsService,
    common_dash_params,
    current_season,
)

MIN_GAMES = 200  # refuse to overwrite calibration on too little data


def _recent_seasons(count: int = 4) -> list[str]:
    """Current season plus the prior few (e.g. ['2025-26','2024-25', ...])."""
    start = int(current_season().split("-")[0])
    return [f"{year}-{str(year + 1)[-2:]}" for year in range(start, start - count, -1)]


def _team_net_ratings(service: LeagueAnalyticsService, season: str) -> dict[int, float]:
    """Map team_id -> average point margin (net rating proxy) for a season."""
    frame = service._stats_frame(
        "leaguedashteamstats",
        common_dash_params(season, "Regular Season", "PerGame"),
        "LeagueDashTeamStats",
    )
    if frame.empty or "TEAM_ID" not in frame or "PLUS_MINUS" not in frame:
        return {}
    nets: dict[int, float] = {}
    for row in frame.to_dict("records"):
        try:
            nets[int(row["TEAM_ID"])] = float(row["PLUS_MINUS"])
        except (TypeError, ValueError):
            continue
    return nets


def _season_games(service: LeagueAnalyticsService, season: str) -> list[dict[str, object]]:
    """Return completed games as {home_id, away_id, home_win} for a season."""
    frame = service._stats_frame(
        "leaguegamelog",
        {
            "LeagueID": "00",
            "Season": season,
            "SeasonType": "Regular Season",
            "PlayerOrTeam": "T",
            "Sorter": "DATE",
            "Direction": "DESC",
            "Counter": "1000",
            "DateFrom": "",
            "DateTo": "",
        },
        "LeagueGameLog",
    )
    if frame.empty or "GAME_ID" not in frame:
        return []

    by_game: dict[str, dict[str, dict[str, object]]] = {}
    for row in frame.to_dict("records"):
        matchup = str(row.get("MATCHUP", ""))
        try:
            team_id = int(row["TEAM_ID"])
        except (TypeError, ValueError):
            continue
        side = "home" if "vs." in matchup else "away"
        by_game.setdefault(str(row["GAME_ID"]), {})[side] = {
            "team_id": team_id,
            "win": str(row.get("WL", "")).upper() == "W",
        }

    games: list[dict[str, object]] = []
    for sides in by_game.values():
        if "home" in sides and "away" in sides:
            games.append(
                {
                    "home_id": sides["home"]["team_id"],
                    "away_id": sides["away"]["team_id"],
                    "home_win": bool(sides["home"]["win"]),
                }
            )
    return games


def _build_dataset(service: LeagueAnalyticsService, seasons: list[str]) -> tuple[np.ndarray, np.ndarray]:
    gaps: list[float] = []
    labels: list[int] = []
    for season in seasons:
        nets = _team_net_ratings(service, season)
        if not nets:
            print(f"  {season}: no team ratings returned, skipping")
            continue
        games = _season_games(service, season)
        used = 0
        for game in games:
            home_id = int(game["home_id"])
            away_id = int(game["away_id"])
            if home_id not in nets or away_id not in nets:
                continue
            gaps.append(nets[home_id] - nets[away_id])
            labels.append(1 if game["home_win"] else 0)
            used += 1
        print(f"  {season}: {used} usable games")
    return np.asarray(gaps, dtype=float), np.asarray(labels, dtype=float)


def _log_loss(gaps: np.ndarray, labels: np.ndarray, hca: float, scale: float) -> float:
    probs = 1.0 / (1.0 + np.exp(-(gaps + hca) / scale))
    probs = np.clip(probs, 1e-6, 1 - 1e-6)
    return float(-np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs)))


def _accuracy(gaps: np.ndarray, labels: np.ndarray, hca: float, scale: float) -> float:
    probs = 1.0 / (1.0 + np.exp(-(gaps + hca) / scale))
    return float(np.mean((probs >= 0.5) == (labels >= 0.5)))


def _fit(gaps: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Grid-search home_court_advantage and scale to minimize log-loss."""
    best = (float("inf"), 2.8, 11.5)
    # Coarse pass, then a refined pass around the winner.
    hca_grid = np.arange(0.0, 5.01, 0.25)
    scale_grid = np.arange(6.0, 16.01, 0.5)
    for _ in range(2):
        for hca in hca_grid:
            for scale in scale_grid:
                loss = _log_loss(gaps, labels, hca, scale)
                if loss < best[0]:
                    best = (loss, float(hca), float(scale))
        _, bh, bs = best
        hca_grid = np.linspace(max(0.0, bh - 0.3), bh + 0.3, 13)
        scale_grid = np.linspace(max(1.0, bs - 0.6), bs + 0.6, 13)
    return best[1], best[2]


def main() -> None:
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    service = LeagueAnalyticsService()

    seasons = _recent_seasons()
    print(f"Downloading real game results for seasons: {', '.join(seasons)}")
    gaps, labels = _build_dataset(service, seasons)

    if len(gaps) < MIN_GAMES:
        print(
            f"\nOnly {len(gaps)} games available (need >= {MIN_GAMES}). "
            "The NBA stats API may be unreachable right now — calibration was NOT changed.\n"
            "The app keeps using its default constants until this succeeds."
        )
        return

    hca, scale = _fit(gaps, labels)
    fit_loss = _log_loss(gaps, labels, hca, scale)
    fit_acc = _accuracy(gaps, labels, hca, scale)

    # Approximate the previous formula (net gap + fixed +1.6 home, /6.5, clipped).
    prev_probs = np.clip(1.0 / (1.0 + np.exp(-(gaps + 1.6) / 6.5)), 0.18, 0.82)
    prev_probs = np.clip(prev_probs, 1e-6, 1 - 1e-6)
    prev_loss = float(-np.mean(labels * np.log(prev_probs) + (1 - labels) * np.log(1 - prev_probs)))
    prev_acc = float(np.mean((prev_probs >= 0.5) == (labels >= 0.5)))

    payload = {
        "home_court_advantage": round(hca, 3),
        "scale": round(scale, 3),
        "fit_log_loss": round(fit_loss, 4),
        "fit_accuracy": round(fit_acc, 4),
        "games_used": int(len(gaps)),
        "seasons": seasons,
        "fit_at": datetime.now(timezone.utc).isoformat(),
    }
    (data_dir / "pregame_calibration.json").write_text(json.dumps(payload, indent=2))

    print("\nCalibration complete:")
    print(f"  games used            : {len(gaps)}")
    print(f"  home court advantage  : {hca:.2f} pts")
    print(f"  margin scale          : {scale:.2f}")
    print(f"  new   accuracy / loss : {fit_acc:.3f} / {fit_loss:.3f}")
    print(f"  old   accuracy / loss : {prev_acc:.3f} / {prev_loss:.3f}  (previous formula, approx)")
    print(f"\nSaved -> {data_dir / 'pregame_calibration.json'}")


if __name__ == "__main__":
    main()
