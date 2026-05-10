from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor


SHOT_FEATURES = ["distance", "angle", "defender_distance", "shot_clock", "game_situation"]


@dataclass(frozen=True)
class ShotContext:
    distance: float
    angle: float
    defender_distance: float
    shot_clock: float
    game_situation: int

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "distance": self.distance,
                    "angle": self.angle,
                    "defender_distance": self.defender_distance,
                    "shot_clock": self.shot_clock,
                    "game_situation": self.game_situation,
                }
            ],
            columns=SHOT_FEATURES,
        )


def _synthetic_shot_training_data(rows: int = 2500, seed: int = 7) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    distance = rng.uniform(1, 31, rows)
    angle = rng.uniform(-55, 55, rows)
    defender_distance = rng.uniform(0, 12, rows)
    shot_clock = rng.uniform(0, 24, rows)
    game_situation = rng.integers(0, 4, rows)

    close_bonus = np.clip((28 - distance) / 28, 0, 1) * 0.38
    open_bonus = np.clip(defender_distance / 10, 0, 1) * 0.22
    clock_bonus = np.clip(shot_clock / 24, 0, 1) * 0.10
    corner_three_bonus = ((distance > 21) & (np.abs(angle) > 35)).astype(float) * 0.05
    clutch_penalty = (game_situation == 3).astype(float) * 0.05
    off_balance_penalty = np.clip(np.abs(angle) / 55, 0, 1) * 0.10
    noise = rng.normal(0, 0.035, rows)

    quality = 0.23 + close_bonus + open_bonus + clock_bonus + corner_three_bonus - clutch_penalty - off_balance_penalty + noise
    quality = np.clip(quality, 0.05, 0.82)

    frame = pd.DataFrame(
        {
            "distance": distance,
            "angle": angle,
            "defender_distance": defender_distance,
            "shot_clock": shot_clock,
            "game_situation": game_situation,
        },
        columns=SHOT_FEATURES,
    )
    return frame, pd.Series(quality, name="shot_quality")


class ShotQualityModel:
    def __init__(self, model_path: Path | str = "data/shot_quality_xgb.joblib") -> None:
        self.model_path = Path(model_path)
        self.model = self._load_or_train()

    def _load_or_train(self) -> XGBRegressor:
        if self.model_path.exists():
            return joblib.load(self.model_path)

        x_train, y_train = _synthetic_shot_training_data()
        model = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=180,
            max_depth=4,
            learning_rate=0.055,
            subsample=0.88,
            colsample_bytree=0.9,
            random_state=7,
        )
        model.fit(x_train, y_train)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self.model_path)
        return model

    def predict(self, context: ShotContext) -> float:
        prediction = float(self.model.predict(context.as_frame())[0])
        return round(float(np.clip(prediction, 0.01, 0.99)), 4)

    def feature_importance(self) -> dict[str, float]:
        scores = getattr(self.model, "feature_importances_", np.zeros(len(SHOT_FEATURES)))
        return {feature: round(float(score), 4) for feature, score in zip(SHOT_FEATURES, scores)}
