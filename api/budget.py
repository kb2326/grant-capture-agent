"""Per-process spending cap for live UI actions (M4 spec §3.1)."""


class SessionBudget:
    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = limit_usd
        self.spent_usd = 0.0

    def allows(self) -> bool:
        return self.spent_usd < self.limit_usd

    def add(self, cost: float) -> None:
        if cost and cost > 0:
            self.spent_usd += cost
