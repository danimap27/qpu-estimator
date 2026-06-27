"""Noise-aware fidelity model using depolarizing + thermal relaxation channels."""

import math
from dataclasses import dataclass

from .models import CircuitProfile, BackendProfile


@dataclass
class NoiseConfig:
    """Configuration for noise modeling."""

    include_depolarizing: bool = True
    include_thermal_relaxation: bool = True
    include_readout: bool = True
    # Coherent error scale factor (experimental)
    coherent_error_scale: float = 1.0


class NoiseAwareFidelityEstimator:
    """
    Estimate circuit fidelity using realistic noise channels.

    Combines:
    - Depolarizing noise from gate errors
    - Thermal relaxation (T1/T2 decay during gate times)
    - Readout errors
    """

    def __init__(self, config: NoiseConfig | None = None):
        self.config = config or NoiseConfig()

    def estimate(
        self,
        circuit_profile: CircuitProfile,
        backend_profile: BackendProfile,
        transpiled_depth: int,
        swap_count: int,
        new_two_qubit_count: int,
    ) -> float:
        """Estimate total circuit fidelity with noise-aware model."""
        fidelity = 1.0

        if self.config.include_depolarizing:
            fidelity *= self._depolarizing_fidelity(
                circuit_profile, backend_profile, new_two_qubit_count
            )

        if self.config.include_thermal_relaxation:
            fidelity *= self._thermal_relaxation_fidelity(
                circuit_profile, backend_profile, transpiled_depth
            )

        if self.config.include_readout:
            fidelity *= self._readout_fidelity(circuit_profile, backend_profile)

        # SWAP penalty for routing complexity
        swap_penalty = max(0.0, 1.0 - swap_count * 0.0005)
        fidelity *= swap_penalty

        return max(0.0, min(1.0, fidelity))

    def _depolarizing_fidelity(
        self,
        circuit_profile: CircuitProfile,
        backend_profile: BackendProfile,
        two_qubit_count: int,
    ) -> float:
        """Fidelity from depolarizing channel based on gate errors."""
        # Single-qubit gates
        avg_sq_error = sum(backend_profile.single_qubit_error) / len(
            backend_profile.single_qubit_error
        )
        sq_fidelity = (1 - avg_sq_error) ** circuit_profile.single_qubit_gates

        # Two-qubit gates
        if backend_profile.two_qubit_error:
            avg_tq_error = sum(backend_profile.two_qubit_error) / len(
                backend_profile.two_qubit_error
            )
        else:
            avg_tq_error = 0.001
        tq_fidelity = (1 - avg_tq_error) ** two_qubit_count

        return sq_fidelity * tq_fidelity

    def _thermal_relaxation_fidelity(
        self,
        circuit_profile: CircuitProfile,
        backend_profile: BackendProfile,
        transpiled_depth: int,
    ) -> float:
        """
        Fidelity from thermal relaxation (T1/T2 decay).

        Uses Lindblad model: F = exp(-t/T1) * exp(-t/T2) for each qubit per layer.
        """
        # Average gate time per layer
        avg_gate_time_ns = sum(backend_profile.gate_times_ns.values()) / len(
            backend_profile.gate_times_ns
        )
        layer_time_us = avg_gate_time_ns / 1000  # convert ns to us

        total_fidelity = 1.0
        for qubit in range(circuit_profile.num_qubits):
            t1 = backend_profile.t1_times_us[qubit]
            t2 = backend_profile.t2_times_us[qubit]

            # Thermal relaxation per layer: e^(-t/T1) * e^(-t/T2_phi)
            # where T2_phi = T2 * T1 / (2*T1 - T2) for pure dephasing
            if 2 * t1 > t2:
                t2_phi = t2 * t1 / (2 * t1 - t2)
            else:
                t2_phi = t2

            # Fidelity per layer: empirically calibrated model
            # Gate times are much shorter than T1/T2, so errors accumulate slowly
            f_t1 = math.exp(-layer_time_us / (2 * t1)) if t1 > 0 else 1.0
            f_t2 = math.exp(-layer_time_us / (2 * t2_phi)) if t2_phi > 0 else 1.0

            # Across all layers
            layer_fidelity = f_t1 * f_t2
            total_fidelity *= layer_fidelity ** transpiled_depth

        return total_fidelity

    def _readout_fidelity(
        self, circuit_profile: CircuitProfile, backend_profile: BackendProfile
    ) -> float:
        """Fidelity from readout errors."""
        avg_ro_error = sum(backend_profile.readout_error) / len(
            backend_profile.readout_error
        )
        return (1 - avg_ro_error) ** circuit_profile.measurement_ops
