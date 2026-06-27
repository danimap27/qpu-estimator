"""Data models for QPU estimation reports."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CircuitProfile:
    """Structural analysis of a quantum circuit."""

    num_qubits: int
    total_gates: int
    single_qubit_gates: int
    two_qubit_gates: int
    depth: int
    measurement_ops: int
    parameterized_gates: int


@dataclass(frozen=True)
class BackendProfile:
    """Hardware profile of a target IBM backend."""

    name: str
    num_qubits: int
    basis_gates: list[str]
    coupling_map: list[list[int]]
    t1_times_us: list[float]       # per qubit
    t2_times_us: list[float]       # per qubit
    single_qubit_error: list[float] # per qubit
    two_qubit_error: list[float]    # per edge (coupling)
    readout_error: list[float]      # per qubit
    gate_times_ns: dict[str, float] # gate name -> duration in ns


@dataclass(frozen=True)
class EstimationReport:
    """Final resource estimation report."""

    backend_name: str
    circuit_profile: CircuitProfile
    transpiled_depth: int
    estimated_execution_time_ms: float
    optimal_shots: int
    estimated_fidelity: float
    estimated_credits: float
    swap_count: int
    notes: list[str]
