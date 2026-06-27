"""Transpilation estimator: predict swap overhead and depth increase."""

import math
from typing import Optional

from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from .models import CircuitProfile, BackendProfile


class TranspilationEstimator:
    """Estimate transpilation overhead using real Qiskit transpilation."""

    def __init__(self, optimization_level: int = 2):
        self.optimization_level = optimization_level

    def estimate(
        self,
        circuit: QuantumCircuit,
        circuit_profile: CircuitProfile,
        backend_profile: BackendProfile,
        use_real_transpiler: bool = True,
    ) -> tuple[int, int, int]:
        """
        Estimate (swap_count, new_depth, new_two_qubit_count).

        If use_real_transpiler is True, runs actual Qiskit transpilation.
        Otherwise falls back to the heuristic from MVP.
        """
        if use_real_transpiler:
            try:
                return self._real_transpile(circuit, backend_profile)
            except Exception:
                pass  # fallback to heuristic

        return self._heuristic_estimate(circuit_profile, backend_profile)

    def _real_transpile(
        self, circuit: QuantumCircuit, backend_profile: BackendProfile
    ) -> tuple[int, int, int]:
        """Run actual Qiskit transpilation and measure overhead."""
        coupling = CouplingMap(backend_profile.coupling_map)
        basis_gates = backend_profile.basis_gates

        pm = generate_preset_pass_manager(
            optimization_level=self.optimization_level,
            coupling_map=coupling,
            basis_gates=basis_gates,
        )
        transpiled = pm.run(circuit)

        # Count SWAPs
        swap_count = sum(
            1 for inst in transpiled.data if inst.operation.name == "swap"
        )

        # Count two-qubit gates
        two_qubit_count = sum(
            1
            for inst in transpiled.data
            if inst.operation.num_qubits == 2 and inst.operation.name != "swap"
        )

        depth = transpiled.depth()

        return swap_count, depth, two_qubit_count

    def _heuristic_estimate(
        self, circuit_profile: CircuitProfile, backend_profile: BackendProfile
    ) -> tuple[int, int, int]:
        """Heuristic fallback from MVP."""
        coupling = CouplingMap(backend_profile.coupling_map)
        avg_distance = self._average_coupling_distance(coupling)

        estimated_swaps = math.ceil(
            circuit_profile.two_qubit_gates * avg_distance * 2
        )
        swap_cnots = estimated_swaps * 3
        new_two_qubit = circuit_profile.two_qubit_gates + swap_cnots
        depth_increase = math.ceil(estimated_swaps * 3 * 0.5)
        new_depth = circuit_profile.depth + depth_increase

        return estimated_swaps, new_depth, new_two_qubit

    @staticmethod
    def _average_coupling_distance(coupling: CouplingMap) -> float:
        """Compute average shortest-path distance between coupled qubits."""
        num_qubits = coupling.size()
        if num_qubits > 2:
            return math.log2(num_qubits) / 2
        return 1.0
