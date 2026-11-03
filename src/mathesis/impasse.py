from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ImpasseFeatures:
    nodes_since_progress: float
    duplicate_state_rate: float
    budget_fraction: float


class ImpasseDetector:
    def __init__(
        self,
        threshold: float = 0.45,
        patience: int = 3,
        window: int = 10,
        budget: int = 100,
        stall_weight: float = 0.5,
        duplicate_weight: float = 0.3,
        # The budget-fraction term is monotone in budget_used, so it pushes the
        # score up late in any search regardless of progress. Default weight is
        # 0.0 (off); to be calibrated on the calibration split later.
        budget_weight: float = 0.0,
    ) -> None:
        if patience < 1:
            raise ValueError("patience must be >= 1")
        self.stall_weight = stall_weight
        self.duplicate_weight = duplicate_weight
        self.budget_weight = budget_weight
        self.threshold = threshold
        self.patience = patience
        self.window = window
        self.budget = budget
        self.nodes_since_progress = 0
        self.recent_duplicates: deque[bool] = deque(maxlen=window)
        self.budget_used = 0
        self.streak = 0
        self.fired = False

    def reset(self) -> None:
        self.nodes_since_progress = 0
        self.recent_duplicates.clear()
        self.budget_used = 0
        self.streak = 0
        self.fired = False

    def score(self) -> float:
        nodes_part = 0.0
        if self.budget > 0:
            nodes_part = self.nodes_since_progress / self.budget
            if nodes_part > 1.0:
                nodes_part = 1.0
        if self.recent_duplicates:
            duplicate_part = sum(1 for item in self.recent_duplicates if item) / len(
                self.recent_duplicates
            )
        else:
            duplicate_part = 0.0
        budget_part = 0.0
        if self.budget > 0:
            budget_part = self.budget_used / self.budget
            if budget_part > 1.0:
                budget_part = 1.0
        return (
            (self.stall_weight * nodes_part)
            + (self.duplicate_weight * duplicate_part)
            + (self.budget_weight * budget_part)
        )

    def features(self) -> ImpasseFeatures:
        nodes_part = 0.0
        if self.budget > 0:
            nodes_part = self.nodes_since_progress / self.budget
            if nodes_part > 1.0:
                nodes_part = 1.0
        if self.recent_duplicates:
            duplicate_part = sum(1 for item in self.recent_duplicates if item) / len(
                self.recent_duplicates
            )
        else:
            duplicate_part = 0.0
        budget_part = 0.0
        if self.budget > 0:
            budget_part = self.budget_used / self.budget
            if budget_part > 1.0:
                budget_part = 1.0
        return ImpasseFeatures(
            nodes_since_progress=nodes_part,
            duplicate_state_rate=duplicate_part,
            budget_fraction=budget_part,
        )

    def update(
        self, made_progress: bool, is_duplicate: bool, budget_used: int
    ) -> bool:
        if made_progress:
            self.nodes_since_progress = 0
        else:
            self.nodes_since_progress += 1
        self.recent_duplicates.append(bool(is_duplicate))
        self.budget_used = int(budget_used)
        current = self.score()
        if current > self.threshold:
            self.streak += 1
        else:
            self.streak = 0
        self.fired = self.streak >= self.patience
        return self.fired

    def in_impasse(self) -> bool:
        return self.fired
