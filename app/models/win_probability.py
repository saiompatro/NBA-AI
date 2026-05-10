from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn


WIN_FEATURES = [
    "score_diff",
    "time_remaining",
    "home_possession",
    "home_fouls",
    "away_fouls",
    "shot_quality",
]


class WinProbabilityNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(len(WIN_FEATURES), 24),
            nn.ReLU(),
            nn.Linear(24, 12),
            nn.ReLU(),
            nn.Linear(12, 1),
            nn.Sigmoid(),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


def normalize_features(values: dict[str, float]) -> np.ndarray:
    return np.array(
        [
            np.clip(values["score_diff"] / 35, -1.5, 1.5),
            np.clip(values["time_remaining"] / 2880, 0, 1),
            values["home_possession"],
            np.clip(values["home_fouls"] / 8, 0, 1.5),
            np.clip(values["away_fouls"] / 8, 0, 1.5),
            np.clip(values["shot_quality"], 0, 1),
        ],
        dtype=np.float32,
    )


def _synthetic_win_training_data(rows: int = 6000, seed: int = 11) -> tuple[torch.Tensor, torch.Tensor]:
    rng = np.random.default_rng(seed)
    time_remaining = rng.uniform(0, 2880, rows)
    score_diff = rng.normal(0, 13, rows) * (0.3 + (1 - time_remaining / 2880))
    home_possession = rng.integers(0, 2, rows)
    home_fouls = rng.integers(0, 7, rows)
    away_fouls = rng.integers(0, 7, rows)
    shot_quality = rng.uniform(0.15, 0.78, rows)

    late_weight = 1.1 + 3.4 * (1 - time_remaining / 2880)
    possession_edge = (home_possession * 2 - 1) * 0.12
    foul_edge = (away_fouls - home_fouls) * 0.04
    shot_edge = (shot_quality - 0.45) * 0.35
    logits = (score_diff / 12) * late_weight + possession_edge + foul_edge + shot_edge
    probability = 1 / (1 + np.exp(-logits))
    labels = rng.binomial(1, probability).astype(np.float32)

    rows_as_dicts = [
        {
            "score_diff": score_diff[i],
            "time_remaining": time_remaining[i],
            "home_possession": home_possession[i],
            "home_fouls": home_fouls[i],
            "away_fouls": away_fouls[i],
            "shot_quality": shot_quality[i],
        }
        for i in range(rows)
    ]
    x = torch.tensor(np.stack([normalize_features(row) for row in rows_as_dicts]), dtype=torch.float32)
    y = torch.tensor(labels.reshape(-1, 1), dtype=torch.float32)
    return x, y


class WinProbabilityModel:
    def __init__(self, model_path: Path | str = "data/win_probability.pt") -> None:
        self.model_path = Path(model_path)
        self.model = WinProbabilityNet()
        self._load_or_train()
        self.model.eval()

    def _load_or_train(self) -> None:
        if self.model_path.exists():
            self.model.load_state_dict(torch.load(self.model_path, map_location="cpu"))
            return

        x_train, y_train = _synthetic_win_training_data()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.012)
        loss_fn = nn.BCELoss()

        self.model.train()
        for _ in range(160):
            optimizer.zero_grad()
            loss = loss_fn(self.model(x_train), y_train)
            loss.backward()
            optimizer.step()

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)

    def predict_home_win_probability(self, values: dict[str, float]) -> float:
        features = torch.tensor(normalize_features(values), dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            probability = float(self.model(features).item())
        return round(float(np.clip(probability, 0.01, 0.99)), 4)
