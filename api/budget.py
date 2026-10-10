"""Per-process spending cap for live UI actions (M4 spec §3.1).

A live call first reserves its estimated cost under a lock, so concurrent requests
cannot all pass the cap; afterwards the estimate is replaced by the real cost. A call
that fails keeps its estimate, since it may have paid before failing.
"""

import threading


class SessionBudget:
    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = limit_usd
        self.spent_usd = 0.0
        self._lock = threading.Lock()

    def allows(self) -> bool:
        return self.spent_usd < self.limit_usd

    def add(self, cost: float) -> None:
        if cost and cost > 0:
            with self._lock:
                self.spent_usd += cost

    def reserve(self, estimate_usd: float) -> bool:
        """Hold `estimate_usd` if it fits under the cap; False means do not call."""
        with self._lock:
            if self.spent_usd + estimate_usd > self.limit_usd:
                return False
            self.spent_usd += estimate_usd
            return True

    def settle(self, estimate_usd: float, actual_usd: float) -> None:
        """Replace a reservation with the real cost."""
        with self._lock:
            self.spent_usd += max(actual_usd, 0.0) - estimate_usd
