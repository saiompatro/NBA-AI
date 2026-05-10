from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.shot_quality import SHOT_FEATURES, ShotQualityModel, _synthetic_shot_training_data
from app.models.win_probability import WinProbabilityModel


def main() -> None:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    shot_model = ShotQualityModel()
    WinProbabilityModel()

    x_train, y_train = _synthetic_shot_training_data()
    training_frame = pd.concat([x_train, y_train], axis=1)
    training_frame.to_csv(data_dir / "synthetic_shot_quality_training.csv", index=False)

    importance = shot_model.feature_importance()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(SHOT_FEATURES, [importance[feature] for feature in SHOT_FEATURES], color="#d96f20")
    ax.set_title("XGBoost Shot Quality Feature Importance")
    ax.set_xlabel("Importance")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(data_dir / "shot_quality_feature_importance.png", dpi=160)
    print("Saved models and diagnostics in data/")


if __name__ == "__main__":
    main()
