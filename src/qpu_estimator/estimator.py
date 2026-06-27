"""Resource estimator: compute time, shots, fidelity, and credits."""

import math
from dataclasses import dataclass

from .models import CircuitProfile, BackendProfile, EstimationReport
from .noise_model import NoiseAwareFidelityEstimator, NoiseConfig
from .shot_optimizer import ShotOptimizer, ShotConfig


@dataclass
class EstimationConfig:
    """Tunable parameters for resource estimation."""

    target_precision: float = 0.01  # For shot estimation
    confidence: float = 0.95  # Hoeffding bound confidence
    min_shots: int = 100
    max_shots: int = 100_000
    ibm_credit_per_second: float = 2.5  # Mock pricing (Phase 1: real table)
    use_noise_aware_fidelity: bool = True
    shot_method: str = "hoeffding"  # hoeffding, chernoff, clopper-pearson


class ResourceEstimator:
    """Estimate execution resources from circuit and backend profiles."""

    def __init__(self, config: EstimationConfig | None = None):
        self.config = config or EstimationConfig()
        self.noise_estimator = NoiseAwareFidelityEstimator(
            NoiseConfig(
                include_depolarizing=True,
                include_thermal_relaxation=True,
                include_readout=True,
            )
        )
        self.shot_optimizer = ShotOptimizer(
            ShotConfig(
                target_precision=self.config.target_precision,
                confidence=self.config.confidence,
                min_shots=self.config.min_shots,
                max_shots=self.config.max_shots,
            )
        )

    def estimate(
        self,
        circuit_profile: CircuitProfile,
        backend_profile: BackendProfile,
        transpiled_depth: int,
        swap_count: int,
        new_two_qubit_count: int,
    ) -> EstimationReport:
        """Produce a full EstimationReport."""
        notes: list[str] = []

        # 1. Execution time
        exec_time_ms = self._estimate_execution_time(
            circuit_profile, backend_profile, transpiled_depth
        )

        # 2. Optimal shots
        self.shot_optimizer.config.target_precision = self.config.target_precision
        self.shot_optimizer.config.confidence = self.config.confidence
        optimal_shots = self.shot_optimizer.optimal_shots(self.config.shot_method)

        # 3. Fidelity (noise-aware or simple)
        if self.config.use_noise_aware_fidelity:
            fidelity = self.noise_estimator.estimate(
                circuit_profile,
                backend_profile,
                transpiled_depth,
                swap_count,
                new_two_qubit_count,
            )
        else:
            fidelity = self._simple_fidelity(
                circuit_profile, backend_profile, new_two_qubit_count, swap_count
            )

        # 4. Credits
        credits = self._estimate_credits(exec_time_ms, optimal_shots)

        # 5. Notes
        if swap_count > 0:
            notes.append(f"Transpilation inserted {swap_count} SWAPs")
        if fidelity < 0.5:
            notes.append("WARNING: estimated fidelity below 50%")
        if transpiled_depth > backend_profile.num_qubits * 2:
            notes.append("WARNING: circuit depth may exceed coherence limits")
        if self.config.use_noise_aware_fidelity:
            notes.append("Noise-aware fidelity model (depolarizing + thermal + readout)")
        notes.append(f"Shot optimization method: {self.config.shot_method}")

        return EstimationReport(
            backend_name=backend_profile.name,
            circuit_profile=circuit_profile,
            transpiled_depth=transpiled_depth,
            estimated_execution_time_ms=exec_time_ms,
            optimal_shots=optimal_shots,
            estimated_fidelity=fidelity,
            estimated_credits=credits,
            swap_count=swap_count,
            notes=notes,
        )

    def _estimate_execution_time(
        self, circuit_profile: CircuitProfile, backend: BackendProfile, depth: int
    ) -> float:
        """Estimate circuit execution time in milliseconds."""
        avg_layer_time = 0.0
        for gate_name, duration_ns in backend.gate_times_ns.items():
            avg_layer_time += duration_ns / len(backend.gate_times_ns)

        measurement_time_ns = circuit_profile.measurement_ops * 1000
        total_ns = depth * avg_layer_time + measurement_time_ns
        return total_ns / 1e6

    def _simple_fidelity(
        self,
        circuit_profile: CircuitProfile,
        backend: BackendProfile,
        two_qubit_count: int,
        swap_count: int,
    ) -> float:
        """Simple product fidelity model (MVP fallback)."""
        avg_sq_error = sum(backend.single_qubit_error) / len(backend.single_qubit_error)
        sq_fidelity = (1 - avg_sq_error) ** circuit_profile.single_qubit_gates

        avg_tq_error = sum(backend.two_qubit_error) / len(backend.two_qubit_error)
        tq_fidelity = (1 - avg_tq_error) ** two_qubit_count

        avg_ro_error = sum(backend.readout_error) / len(backend.readout_error)
        ro_fidelity = (1 - avg_ro_error) ** circuit_profile.measurement_ops

        swap_penalty = max(0.0, 1.0 - swap_count * 0.005)
        return max(0.0, min(1.0, sq_fidelity * tq_fidelity * ro_fidelity * swap_penalty))

    def _estimate_credits(self, exec_time_ms: float, shots: int) -> float:
        """Estimate IBM Runtime credits (mock pricing)."""
        time_seconds = exec_time_ms / 1000
        return time_seconds * shots * self.config.ibm_credit_per_second / 1000
