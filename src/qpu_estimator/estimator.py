"""Resource estimator: compute time, shots, fidelity, and credits."""

import math
from dataclasses import dataclass

from .models import CircuitProfile, BackendProfile, EstimationReport


@dataclass
class EstimationConfig:
    """Tunable parameters for resource estimation."""

    target_precision: float = 0.01          # For shot estimation
    confidence: float = 0.95                # Hoeffding bound confidence
    min_shots: int = 100
    max_shots: int = 100_000
    ibm_credit_per_second: float = 2.5      # Mock pricing (Phase 1: real table)


class ResourceEstimator:
    """Estimate execution resources from circuit and backend profiles."""

    def __init__(self, config: EstimationConfig | None = None):
        self.config = config or EstimationConfig()

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
        optimal_shots = self._estimate_shots(circuit_profile)

        # 3. Fidelity
        fidelity = self._estimate_fidelity(
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
        # Sum gate times per layer (depth)
        avg_layer_time = 0.0
        for gate_name, duration_ns in backend.gate_times_ns.items():
            # Rough: assume each layer has a mix of gates
            avg_layer_time += duration_ns / len(backend.gate_times_ns)

        # Measurement time (roughly 1 us per qubit)
        measurement_time_ns = circuit_profile.measurement_ops * 1000

        total_ns = depth * avg_layer_time + measurement_time_ns
        return total_ns / 1e6  # convert to ms

    def _estimate_shots(self, circuit_profile: CircuitProfile) -> int:
        """Estimate optimal shot count using Hoeffding bound."""
        # For a single binary observable, Hoeffding: n >= ln(2/delta)/(2*eps^2)
        eps = self.config.target_precision
        delta = 1 - self.config.confidence
        n = math.ceil(math.log(2 / delta) / (2 * eps * eps))
        return max(self.config.min_shots, min(n, self.config.max_shots))

    def _estimate_fidelity(
        self,
        circuit_profile: CircuitProfile,
        backend: BackendProfile,
        two_qubit_count: int,
        swap_count: int,
    ) -> float:
        """Estimate circuit fidelity using a simple product model."""
        # Single-qubit gate fidelity
        avg_sq_error = sum(backend.single_qubit_error) / len(backend.single_qubit_error)
        sq_fidelity = (1 - avg_sq_error) ** circuit_profile.single_qubit_gates

        # Two-qubit gate fidelity
        avg_tq_error = sum(backend.two_qubit_error) / len(backend.two_qubit_error)
        tq_fidelity = (1 - avg_tq_error) ** two_qubit_count

        # Readout fidelity
        avg_ro_error = sum(backend.readout_error) / len(backend.readout_error)
        ro_fidelity = (1 - avg_ro_error) ** circuit_profile.measurement_ops

        # SWAP overhead: each swap is 3 CNOTs, already counted in two_qubit_count
        # but we add a small penalty for routing complexity
        swap_penalty = max(0.0, 1.0 - swap_count * 0.005)

        total_fidelity = sq_fidelity * tq_fidelity * ro_fidelity * swap_penalty
        return max(0.0, min(1.0, total_fidelity))

    def _estimate_credits(self, exec_time_ms: float, shots: int) -> float:
        """Estimate IBM Runtime credits (mock pricing)."""
        # Rough model: credits scale with time * shots
        time_seconds = exec_time_ms / 1000
        return time_seconds * shots * self.config.ibm_credit_per_second / 1000
