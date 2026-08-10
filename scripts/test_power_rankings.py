"""Self-check for the power-rankings blurb generator.

Run directly: python scripts/test_power_rankings.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import power_ranking_blurb


def _team(name: str = "Test Team", net: float = 0.0) -> dict:
    return {"team": name, "net": net}


def main() -> None:
    elite = power_ranking_blurb(_team(net=8.0), form_pct=0.9, movement=0)
    assert "elite two-way" in elite, "a strongly positive net rating should read as elite two-way"
    assert "riding a hot streak" in elite, "9/10 recent form should read as a hot streak"

    cold = power_ranking_blurb(_team(net=-3.0), form_pct=0.1, movement=0)
    assert "still trending negative" in cold, "a negative net rating must not be described as elite or positive"
    assert "cold over their last 10" in cold, "1/10 recent form should read as cold"

    over_ranked = power_ranking_blurb(_team(net=1.0), form_pct=0.5, movement=5)
    assert "above their record" in over_ranked, "positive movement should read as ranked above the team's record"

    under_ranked = power_ranking_blurb(_team(net=1.0), form_pct=0.5, movement=-5)
    assert "below their record" in under_ranked, "negative movement should read as ranked below the team's record"

    neutral = power_ranking_blurb(_team(net=1.0), form_pct=0.5, movement=1)
    assert "about where their record says" in neutral, "small movement should read as roughly matching the record"

    print("OK: power-ranking blurbs are signed correctly for net rating, form, and record movement")


if __name__ == "__main__":
    main()
