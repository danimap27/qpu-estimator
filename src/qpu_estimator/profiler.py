"""Backend profiler: build hardware profiles for IBM backends."""

from typing import Optional

from .models import BackendProfile


class BackendProfiler:
    """Create BackendProfile instances from IBM backend names."""

    # Mock profiles for offline fallback
    _MOCK_PROFILES: dict[str, dict] = {
        "ibm_heron": {
            "num_qubits": 133,
            "basis_gates": ["rz", "sx", "x", "ecr"],
            "coupling_map": [[i, i + 1] for i in range(132)],
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

    def __init__(self, use_live: bool = True, token: Optional[str] = None):
        self.use_live = use_live
        self._token = token
        self._live_cache: dict[str, BackendProfile] = {}

    def _get_live_profile(self, backend_name: str) -> BackendProfile:
        """Fetch live profile from IBM Quantum Runtime."""
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService

            service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=self._token or self._get_token(),
            )
            backend = service.backend(backend_name)
            props = backend.properties()
            config = backend.configuration()

            # Extract calibration data with error handling
            t1_list = []
            t2_list = []
            ro_list = []
            sq_errors = []

            for i in range(config.n_qubits):
                # T1
                try:
                    t1_list.append(props.t1(i) * 1e6)
                except Exception:
                    t1_list.append(100.0)

                # T2
                try:
                    t2_list.append(props.t2(i) * 1e6)
                except Exception:
                    t2_list.append(t1_list[-1] * 0.5)

                # Readout error
                try:
                    ro_list.append(props.readout_error(i))
                except Exception:
                    ro_list.append(0.01)

                # Single-qubit gate error (average of rz, sx, x)
                sq_errs = []
                for gate in config.basis_gates:
                    if gate in ("id", "rz"):
                        continue  # rz and id are virtual/error-free
                    try:
                        err = props.gate_error(gate, i)
                        sq_errs.append(err)
                    except Exception:
                        pass
                sq_errors.append(
                    sum(sq_errs) / len(sq_errs) if sq_errs else 0.001
                )

            # Two-qubit gate errors
            tq_errors = []
            tq_edges = []
            tq_gate = next(
                (g for g in config.basis_gates if g not in ("id", "rz", "sx", "x")),
                "cz",
            )

            for edge in config.coupling_map:
                if edge[0] < edge[1]:  # avoid duplicates
                    try:
                        err = props.gate_error(tq_gate, edge)
                        tq_errors.append(err)
                        tq_edges.append(edge)
                    except Exception:
                        pass

            # Gate times (mock defaults since IBM doesn't expose per-gate durations easily)
            gate_times = {"rz": 0.0, "sx": 35.0, "x": 35.0}
            if tq_gate == "ecr":
                gate_times["ecr"] = 660.0
            elif tq_gate == "cz":
                gate_times["cz"] = 500.0
            else:
                gate_times[tq_gate] = 500.0

            profile = BackendProfile(
                name=backend_name,
                num_qubits=config.n_qubits,
                basis_gates=list(config.basis_gates),
                coupling_map=list(config.coupling_map),
                t1_times_us=t1_list,
                t2_times_us=t2_list,
                single_qubit_error=sq_errors,
                two_qubit_error=tq_errors,
                readout_error=ro_list,
                gate_times_ns=gate_times,
            )
            self._live_cache[backend_name] = profile
            return profile

        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch live profile for {backend_name}: {exc}"
            ) from exc

    @staticmethod
    def _get_token() -> str:
        import os

        token = os.environ.get("QISKIT_IBM_TOKEN")
        if not token:
            raise RuntimeError(
                "IBM Quantum token not found. Set QISKIT_IBM_TOKEN environment variable."
            )
        return token

    def get_profile(self, backend_name: str) -> BackendProfile:
        """Return a BackendProfile for *backend_name*."""
        if self.use_live:
            try:
                return self._get_live_profile(backend_name)
            except Exception:
                pass  # fallback to mock

        if backend_name not in self._MOCK_PROFILES:
            raise ValueError(
                f"Unknown backend: {backend_name}. "
                f"Available: {list(self._MOCK_PROFILES.keys())}"
            )
        data = self._MOCK_PROFILES[backend_name]
        return BackendProfile(name=backend_name, **data)

    def list_backends(self) -> list[str]:
        """Return all known backend names."""
        return list(self._MOCK_PROFILES.keys())

    def list_live_backends(self) -> list[str]:
        """Return all live backends from IBM Quantum."""
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService

            service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=self._token or self._get_token(),
            )
            return [b.name for b in service.backends()]
        except Exception:
            return []
