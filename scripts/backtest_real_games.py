from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.shot_quality import ShotContext, ShotQualityModel
from app.models.win_probability import WinProbabilityModel


_SHOT_EVENTS_PATH = Path("data/real_shot_events_2023.csv")
_GAME_SNAPSHOTS_PATH = Path("data/real_game_snapshots_2023.csv")
_OUTPUT_PATH = Path("data/live_model_backtest.json")

# (label, min_distance_ft, max_distance_ft) - max is inclusive; None means unbounded.
_DISTANCE_BUCKETS = [
    ("0-3 ft", 0, 3),
    ("4-9 ft", 4, 9),
    ("10-15 ft", 10, 15),
    ("16-21 ft", 16, 21),
    ("22-23 ft", 22, 23),
    ("24+ ft", 24, None),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0
    return cov / denom


def backtest_shot_quality(shot_model: ShotQualityModel) -> dict:
    rows = _read_csv(_SHOT_EVENTS_PATH)
    distances = [float(row["distance_ft"]) for row in rows]
    makes = [int(row["made"]) for row in rows]
    overall_real_fg_pct = sum(makes) / len(makes) if makes else 0.0

    buckets = []
    real_rates = []
    predicted_qualities = []
    for label, low, high in _DISTANCE_BUCKETS:
        bucket_indices = [
            i
            for i, d in enumerate(distances)
            if d >= low and (high is None or d <= high)
        ]
        n = len(bucket_indices)
        if n == 0:
            continue
        bucket_makes = [makes[i] for i in bucket_indices]
        bucket_distances = [distances[i] for i in bucket_indices]
        real_fg_pct = sum(bucket_makes) / n
        mean_distance = sum(bucket_distances) / n
        predicted_quality = shot_model.predict(
            ShotContext(
                distance=mean_distance,
                angle=0.0,
                defender_distance=6.0,
                shot_clock=12.0,
                game_situation=0,
            )
        )
        buckets.append(
            {
                "label": label,
                "n": n,
                "real_fg_pct": round(real_fg_pct, 4),
                "predicted_quality": predicted_quality,
            }
        )
        real_rates.append(real_fg_pct)
        predicted_qualities.append(predicted_quality)

    correlation = _pearson_correlation(real_rates, predicted_qualities)

    return {
        "overall_real_fg_pct": round(overall_real_fg_pct, 4),
        "buckets": buckets,
        "correlation_real_fg_vs_predicted_quality": round(correlation, 4),
    }, len(rows)


def backtest_win_probability(shot_model: ShotQualityModel, win_model: WinProbabilityModel) -> dict:
    rows = _read_csv(_GAME_SNAPSHOTS_PATH)

    predictions = []
    actuals = []
    by_game: dict[str, list[tuple[float, int]]] = {}

    for row in rows:
        shot_x = float(row["shot_x"])
        shot_y = float(row["shot_y"])
        angle_deg = math.degrees(math.atan2(shot_x, shot_y))
        angle_deg = max(-89.0, min(89.0, angle_deg))

        shot_quality = shot_model.predict(
            ShotContext(
                distance=float(row["shot_distance_ft"]),
                angle=angle_deg,
                defender_distance=6.0,
                shot_clock=12.0,
                game_situation=0,
            )
        )
        predicted_prob = win_model.predict_home_win_probability(
            {
                "score_diff": float(row["score_diff"]),
                "time_remaining": float(row["time_remaining_sec"]),
                "home_possession": 0.5,
                "home_fouls": 3,
                "away_fouls": 3,
                "shot_quality": shot_quality,
            }
        )
        home_win = int(row["home_win"])
        predictions.append(predicted_prob)
        actuals.append(home_win)
        by_game.setdefault(row["game_id"], []).append((predicted_prob, home_win))

    eps = 1e-6
    clipped = [min(max(p, eps), 1 - eps) for p in predictions]
    log_loss = -sum(
        y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(clipped, actuals)
    ) / len(actuals)
    brier_score = sum((p - y) ** 2 for p, y in zip(predictions, actuals)) / len(actuals)

    correct = 0
    total_games = 0
    for game_rows in by_game.values():
        total_games += 1
        final_prob, final_actual = game_rows[-1]
        predicted_winner = 1 if final_prob > 0.5 else 0
        if predicted_winner == final_actual:
            correct += 1

    return {
        "checkpoints": len(rows),
        "log_loss": round(log_loss, 4),
        "brier_score": round(brier_score, 4),
        "final_checkpoint_accuracy": f"{correct}/{total_games}",
        "note": (
            "home_possession and foul counts are held at neutral placeholder values "
            "(not reconstructed from the source data in this sample) - this backtest "
            "isolates the model's response to real score_diff, time_remaining, and "
            "shot_quality."
        ),
    }


def main() -> None:
    shot_model = ShotQualityModel()
    win_model = WinProbabilityModel()

    shot_quality_results, shots_backtested = backtest_shot_quality(shot_model)
    win_probability_results = backtest_win_probability(shot_model, win_model)

    output = {
        "source": "brendanwilliam/nba-playbyplay-2223season (Hugging Face Hub)",
        "sample_size_caveat": (
            "2 real games, 329 real shots, hand-extracted; small-N directional signal, "
            "not a statistically powered backtest - extend by adding more games to the "
            "two CSVs in data/"
        ),
        "games": 2,
        "shots_backtested": shots_backtested,
        "shot_quality": shot_quality_results,
        "win_probability": win_probability_results,
    }

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2))

    print("Real-game backtest complete")
    print(f"  Shots backtested: {shots_backtested} across {output['games']} games")
    print(f"  Overall real FG%: {shot_quality_results['overall_real_fg_pct'] * 100:.1f}%")
    print("  Shot-quality buckets (real FG% vs. predicted quality):")
    for bucket in shot_quality_results["buckets"]:
        print(
            f"    {bucket['label']:>9}  n={bucket['n']:<4} "
            f"real_fg={bucket['real_fg_pct']:.3f}  predicted_quality={bucket['predicted_quality']:.3f}"
        )
    print(
        f"  Correlation (real FG% vs. predicted quality): "
        f"{shot_quality_results['correlation_real_fg_vs_predicted_quality']:.4f}"
    )
    print()
    print(f"  Win-probability checkpoints: {win_probability_results['checkpoints']}")
    print(f"  Log loss: {win_probability_results['log_loss']:.4f}")
    print(f"  Brier score: {win_probability_results['brier_score']:.4f}")
    print(f"  Final-checkpoint accuracy: {win_probability_results['final_checkpoint_accuracy']}")
    print()
    print(f"Wrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
