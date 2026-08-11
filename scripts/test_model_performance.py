"""Self-check for LeagueAnalyticsService.model_performance().

Run directly: python scripts/test_model_performance.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services import league_analytics
from app.services.league_analytics import LeagueAnalyticsService


def main() -> None:
    service = LeagueAnalyticsService()
    original_path = league_analytics._CALIBRATION_PATH

    try:
        # --- Not yet calibrated: file missing ---
        league_analytics._CALIBRATION_PATH = Path(tempfile.mkdtemp()) / "missing.json"
        uncalibrated = service.model_performance()
        assert uncalibrated["calibrated"] is False, "missing calibration file must report calibrated=False"
        assert uncalibrated["accuracy"] is None, "missing calibration file must not fabricate an accuracy number"

        # --- Calibrated: fitted file present ---
        fitted = Path(tempfile.mkdtemp()) / "pregame_calibration.json"
        fitted.write_text(json.dumps({
            "home_court_advantage": 2.3,
            "scale": 7.9,
            "fit_log_loss": 0.5954,
            "fit_accuracy": 0.6815,
            "games_used": 3680,
            "seasons": ["2025-26", "2024-25"],
            "fit_at": "2026-05-31T06:11:52+00:00",
        }))
        league_analytics._CALIBRATION_PATH = fitted
        perf = service.model_performance()
        assert perf["calibrated"] is True
        assert perf["accuracy"] == 0.6815
        assert perf["games_backtested"] == 3680
        assert perf["baseline_home_win_rate"] < perf["accuracy"], "model should be presented as beating the naive baseline"
        assert len(perf["inputs"]) > 0
    finally:
        league_analytics._CALIBRATION_PATH = original_path

    print("OK: model_performance reports calibrated=False with no fabricated numbers, and surfaces the fitted backtest otherwise")


if __name__ == "__main__":
    main()
