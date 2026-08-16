"""Self-check for the four-factors (eFG% / TOV% / OREB% / FT rate) pregame adjustment.

Run directly: python scripts/test_four_factors.py
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

from app.services.league_analytics import (
    _FOUR_FACTORS_CAP,
    four_factors_edge,
)


def main() -> None:
    # Identical shooting/turnover profiles add nothing.
    assert four_factors_edge(53.0, 53.0, 13.0, 13.0) == 0.0

    # Home team shoots better (higher eFG%) -> positive (home-favoring) edge.
    edge = four_factors_edge(home_efg=56.0, away_efg=52.0, home_tov=13.0, away_tov=13.0)
    assert edge > 0, "a home eFG% advantage should help the home side"

    # Home team turns it over more (higher TOV%) -> negative (away-favoring) edge.
    edge = four_factors_edge(home_efg=53.0, away_efg=53.0, home_tov=16.0, away_tov=12.0)
    assert edge < 0, "a home turnover-rate disadvantage should hurt the home side"

    # The two factors combine additively before the cap is applied.
    combined = four_factors_edge(home_efg=55.0, away_efg=53.0, home_tov=12.0, away_tov=14.0)
    shooting_only = four_factors_edge(home_efg=55.0, away_efg=53.0, home_tov=13.0, away_tov=13.0)
    ball_only = four_factors_edge(home_efg=53.0, away_efg=53.0, home_tov=12.0, away_tov=14.0)
    assert abs(combined - (shooting_only + ball_only)) < 1e-9

    # Extreme gaps must stay capped.
    edge = four_factors_edge(home_efg=70.0, away_efg=30.0, home_tov=5.0, away_tov=25.0)
    assert edge == _FOUR_FACTORS_CAP, "edge must clamp at the positive cap"
    edge = four_factors_edge(home_efg=30.0, away_efg=70.0, home_tov=25.0, away_tov=5.0)
    assert edge == -_FOUR_FACTORS_CAP, "edge must clamp at the negative cap"

    # OREB% and FT rate default to 0 - two-factor call sites are unaffected.
    two_factor = four_factors_edge(home_efg=55.0, away_efg=53.0, home_tov=12.0, away_tov=14.0)
    explicit_zero = four_factors_edge(
        home_efg=55.0, away_efg=53.0, home_tov=12.0, away_tov=14.0,
        home_oreb=0.0, away_oreb=0.0, home_ftr=0.0, away_ftr=0.0,
    )
    assert two_factor == explicit_zero

    # A rebounding edge (more extra shots) favors the home side.
    edge = four_factors_edge(53.0, 53.0, 13.0, 13.0, home_oreb=32.0, away_oreb=24.0)
    assert edge > 0, "a home offensive-rebounding advantage should help the home side"

    # A free-throw-rate edge (more trips to the line) favors the home side.
    edge = four_factors_edge(53.0, 53.0, 13.0, 13.0, home_ftr=26.0, away_ftr=18.0)
    assert edge > 0, "a home FT-rate advantage should help the home side"

    # All four factors combine additively before the cap is applied (kept well under
    # the cap so clamping doesn't mask the additivity check).
    combined = four_factors_edge(55.0, 53.0, 12.0, 14.0, 30.0, 28.0, 22.0, 18.0)
    parts = (
        four_factors_edge(55.0, 53.0, 13.0, 13.0)
        + four_factors_edge(53.0, 53.0, 12.0, 14.0)
        + four_factors_edge(53.0, 53.0, 13.0, 13.0, home_oreb=30.0, away_oreb=28.0)
        + four_factors_edge(53.0, 53.0, 13.0, 13.0, home_ftr=22.0, away_ftr=18.0)
    )
    assert abs(combined - parts) < 1e-9

    print("OK: four-factors edge covers eFG%/TOV%/OREB%/FT-rate, is zero on identical profiles, signed correctly, additive, and capped")


if __name__ == "__main__":
    main()
