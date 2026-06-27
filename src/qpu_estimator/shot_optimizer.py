"""Shot optimization using statistical bounds."""

import math
from dataclasses import dataclass

from .models import CircuitProfile


@dataclass
class ShotConfig:
    """Configuration for shot optimization."""

    target_precision: float = 0.01
    confidence: float = 0.95
    min_shots: int = 100
    max_shots: int = 100_000
    # For multi-shot observable estimation
    num_observables: int = 1


class ShotOptimizer:
    """
    Optimize shot count using statistical bounds.

    Supports:
    - Hoeffding bound (default, conservative)
    - Chernoff bound (for small probabilities)
    - Clopper-Pearson exact (for binomial proportions)
    """

    def __init__(self, config: ShotConfig | None = None):
        self.config = config or ShotConfig()

    def optimal_shots(self, method: str = "hoeffding") -> int:
        """Calculate optimal shot count using specified method."""
        if method == "hoeffding":
            return self._hoeffding_shots()
        elif method == "chernoff":
            return self._chernoff_shots()
        elif method == "clopper-pearson":
            return self._clopper_pearson_shots()
        else:
            raise ValueError(f"Unknown method: {method}")

    def _hoeffding_shots(self) -> int:
        """
        Hoeffding bound: P(|mean - true| > eps) < 2*exp(-2*n*eps^2).

        Solve for n: n > ln(2/delta) / (2*eps^2)
        """
        eps = self.config.target_precision
        delta = 1 - self.config.confidence
        n = math.ceil(math.log(2 / delta) / (2 * eps * eps))
        # Scale for multiple observables
        n *= self.config.num_observables
        return max(self.config.min_shots, min(n, self.config.max_shots))

    def _chernoff_shots(self) -> int:
        """
        Chernoff bound for small probabilities:
        P(|p_hat - p| > eps*p) < 2*exp(-n*eps^2*p / 3)

        Assume p ~ 0.5 for worst case.
        """
        eps = self.config.target_precision
        delta = 1 - self.config.confidence
        p = 0.5  # worst-case probability
        n = math.ceil(3 * math.log(2 / delta) / (eps * eps * p))
        n *= self.config.num_observables
        return max(self.config.min_shots, min(n, self.config.max_shots))

    def _clopper_pearson_shots(self) -> int:
        """
        Clopper-Pearson exact confidence interval for binomial proportion.

        Uses normal approximation for large n.
        """
        eps = self.config.target_precision
        z = self._z_score(self.config.confidence)
        p = 0.5  # worst case
        n = math.ceil((z / eps) ** 2 * p * (1 - p))
        n *= self.config.num_observables
        return max(self.config.min_shots, min(n, self.config.max_shots))

    @staticmethod
    def _z_score(confidence: float) -> float:
        """Z-score for given confidence level (normal approximation)."""
        # Common values: 0.95 -> 1.96, 0.99 -> 2.576
        scores = {0.90: 1.282, 0.95: 1.96, 0.99: 2.576, 0.999: 3.291}
        return scores.get(confidence, 1.96)

    def precision_for_shots(self, shots: int, method: str = "hoeffding") -> float:
        """Calculate achievable precision for given shot count."""
        if method == "hoeffding":
            delta = 2 * math.exp(-2 * shots * self.config.target_precision**2)
            return math.sqrt(math.log(2 / (1 - self.config.confidence)) / (2 * shots))
        return self.config.target_precision
