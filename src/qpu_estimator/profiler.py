"""Backend profiler: build hardware profiles for IBM backends."""

from .models import BackendProfile


class BackendProfiler:
    """Create BackendProfile instances from IBM backend names."""

    # Mock profiles for MVP — Phase 1 will fetch live data from IBM Runtime
    _MOCK_PROFILES: dict[str, dict] = {
        "ibm_heron": {
            "num_qubits": 133,
            "basis_gates": ["rz", "sx", "x", "ecr"],
            "coupling_map": [[i, i + 1] for i in range(132)],  # linear chain mock
            "t1_times_us": [100.0] * 133,
            "t2_times_us": [150.0] * 133,
            "single_qubit_error": [0.0002] * 133,
            "two_qubit_error": [0.001] * 132,
            "readout_error": [0.01] * 133,
            "gate_times_ns": {"rz": 0.0, "sx": 35.0, "x": 35.0, "ecr": 660.0},
        },
        "ibm_brisbane": {
            "num_qubits": 127,
            "basis_gates": ["rz", "sx", "x", "ecr"],
            "coupling_map": [[i, i + 1] for i in range(126)],
            "t1_times_us": [120.0] * 127,
            "t2_times_us": [180.0] * 127,
            "single_qubit_error": [0.0003] * 127,
            "two_qubit_error": [0.0015] * 126,
            "readout_error": [0.015] * 127,
            "gate_times_ns": {"rz": 0.0, "sx": 40.0, "x": 40.0, "ecr": 700.0},
        },
        "ibm_sherbrooke": {
            "num_qubits": 127,
            "basis_gates": ["rz", "sx", "x", "ecr"],
            "coupling_map": [[i, i + 1] for i in range(126)],
            "t1_times_us": [80.0] * 127,
            "t2_times_us": [100.0] * 127,
            "single_qubit_error": [0.0005] * 127,
            "two_qubit_error": [0.002] * 126,
            "readout_error": [0.02] * 127,
            "gate_times_ns": {"rz": 0.0, "sx": 50.0, "x": 50.0, "ecr": 800.0},
        },
    }

    def get_profile(self, backend_name: str) -> BackendProfile:
        """Return a BackendProfile for *backend_name*."""
        if backend_name not in self._MOCK_PROFILES:
            raise ValueError(f"Unknown backend: {backend_name}. "
                             f"Available: {list(self._MOCK_PROFILES.keys())}")
        data = self._MOCK_PROFILES[backend_name]
        return BackendProfile(name=backend_name, **data)

    def list_backends(self) -> list[str]:
        """Return all known backend names."""
        return list(self._MOCK_PROFILES.keys())
