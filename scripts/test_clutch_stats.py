"""Self-check for clutch-time team-stats fallback (last 5 min, score within 5 pts).

Run directly: python scripts/test_clutch_stats.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Stub out the `app`/`app.services` packages before importing league_analytics so this
# check doesn't drag in app/__init__.py -> app.main -> torch (unrelated to this logic
# and not always installable/loadable in every environment).
for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import clutch_fallback


def main() -> None:
    even = clutch_fallback(0.0)
    assert even["clutch_record"] == "0-0", "clutch record fallback is always a neutral placeholder"
    assert even["clutch_net"] == 0.0, "a net-neutral team must have a net-neutral clutch fallback"

    strong = clutch_fallback(9.0)
    weak = clutch_fallback(-9.0)
    assert strong["clutch_net"] > 0 > weak["clutch_net"], "fallback clutch net must track season net rating direction"
    assert strong["clutch_net"] == 3.0 and weak["clutch_net"] == -3.0, "fallback clutch net is net rating / 3"

    for stats in (even, strong, weak):
        assert set(stats) == {"clutch_record", "clutch_net"}

    print("OK: clutch-stats fallback is internally consistent with net rating")


if __name__ == "__main__":
    main()
