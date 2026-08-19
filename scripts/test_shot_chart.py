"""Self-check for the shot-chart per-zone breakdown.

Run directly: python scripts/test_shot_chart.py
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

from app.services.league_analytics import shot_zone_breakdown


def main() -> None:
    assert shot_zone_breakdown([]) == [], "no shots must produce no zone rows"

    shots = [
        {"zone": "Restricted Area", "made": True},
        {"zone": "Restricted Area", "made": True},
        {"zone": "Restricted Area", "made": False},
        {"zone": "Above the Break 3", "made": True},
        {"zone": "Above the Break 3", "made": False},
    ]
    zones = shot_zone_breakdown(shots)
    by_zone = {row["zone"]: row for row in zones}

    assert by_zone["Restricted Area"]["attempts"] == 3
    assert by_zone["Restricted Area"]["made"] == 2
    assert by_zone["Restricted Area"]["pct"] == round(2 / 3 * 100, 1)

    assert by_zone["Above the Break 3"]["attempts"] == 2
    assert by_zone["Above the Break 3"]["made"] == 1
    assert by_zone["Above the Break 3"]["pct"] == 50.0

    # Higher-volume zone must sort first.
    assert zones[0]["zone"] == "Restricted Area", "zones must sort by attempt volume, highest first"

    print("OK: shot-chart zone breakdown aggregates and sorts correctly")


if __name__ == "__main__":
    main()
