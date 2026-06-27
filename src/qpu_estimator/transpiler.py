"""Transpilation estimator: predict swap overhead and depth increase."""

import math
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from .models import CircuitProfile, BackendProfile


class TranspilationEstimator:
    """Estimate transpilation overhead without full transpilation."""

    def estimate(
        self, circuit_profile: CircuitProfile, backend_profile: BackendProfile
    ) -> tuple[int, int, int]:
        """
        Estimate (swap_count, new_depth, new_two_qubit_count).

        Uses a simple heuristic: each two-qubit gate spanning >1 hop on the
        coupling map inserts ~2*distance swaps on average.
        """
        coupling = CouplingMap(backend_profile.coupling_map)
        avg_distance = self._average_coupling_distance(coupling)

        # Heuristic: each non-local CNOT needs ~2 swaps per hop
        estimated_swaps = math.ceil(circuit_profile.two_qubit_gates * avg_distance * 2)

        # Each swap adds 3 CNOTs to the circuit
        swap_cnots = estimated_swaps * 3
        new_two_qubit = circuit_profile.two_qubit_gates + swap_cnots

        # Depth increase: swaps are on critical path ~50% of the time
        depth_increase = math.ceil(estimated_swaps * 3 * 0.5)
        new_depth = circuit_profile.depth + depth_increase

        return estimated_swaps, new_depth, new_two_qubit

    @staticmethod
    def _average_coupling_distance(coupling: CouplingMap) -> float:
        """Compute average shortest-path distance between coupled qubits."""
        distances = []
        for edge in coupling.get_edges():
            # In a real implementation we'd use BFS from each node;
            # for MVP we approximate with a constant based on topology.
            distances.append(1.0)
        # Add some non-local pairs to model realistic routing
        num_qubits = coupling.size()
        if num_qubits > 2:
            # Approximate average distance on a grid/chain
            return math.log2(num_qubits) / 2
        return 1.0
