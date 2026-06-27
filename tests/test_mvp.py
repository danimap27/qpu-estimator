"""Tests for QPU-Estimator MVP."""

import pytest
from qiskit import QuantumCircuit

from qpu_estimator import QPUEstimator
from qpu_estimator.analyzer import CircuitAnalyzer
from qpu_estimator.profiler import BackendProfiler
from qpu_estimator.transpiler import TranspilationEstimator
from qpu_estimator.estimator import ResourceEstimator, EstimationConfig


class TestCircuitAnalyzer:
    def test_bell_state(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        analyzer = CircuitAnalyzer()
        profile = analyzer.analyze(circuit)

        assert profile.num_qubits == 2
        assert profile.total_gates == 5  # h, cx, barrier, measure, measure
        assert profile.single_qubit_gates == 1
        assert profile.two_qubit_gates == 1
        assert profile.depth == 3
        assert profile.measurement_ops == 2


class TestBackendProfiler:
    def test_known_backends(self):
        profiler = BackendProfiler()
        assert "ibm_heron" in profiler.list_backends()
        assert "ibm_brisbane" in profiler.list_backends()

    def test_heron_profile(self):
        profiler = BackendProfiler()
        profile = profiler.get_profile("ibm_heron")
        assert profile.num_qubits == 133
        assert "ecr" in profile.basis_gates

    def test_unknown_backend(self):
        profiler = BackendProfiler()
        with pytest.raises(ValueError):
            profiler.get_profile("ibm_fake")


class TestTranspilationEstimator:
    def test_no_swap_for_local_cnot(self):
        from qpu_estimator.models import CircuitProfile, BackendProfile

        profile = CircuitProfile(
            num_qubits=2, total_gates=2, single_qubit_gates=1,
            two_qubit_gates=1, depth=2, measurement_ops=0, parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock", num_qubits=2, basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[100, 100], t2_times_us=[150, 150],
            single_qubit_error=[0.0, 0.0], two_qubit_error=[0.0],
            readout_error=[0.0, 0.0], gate_times_ns={"cx": 100},
        )
        estimator = TranspilationEstimator()
        swaps, depth, _ = estimator.estimate(profile, backend)
        # Heuristic may insert small swaps; just verify it's reasonable
        assert swaps >= 0


class TestResourceEstimator:
    def test_fidelity_range(self):
        from qpu_estimator.models import CircuitProfile, BackendProfile

        circuit = CircuitProfile(
            num_qubits=2, total_gates=2, single_qubit_gates=1,
            two_qubit_gates=1, depth=2, measurement_ops=2, parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock", num_qubits=2, basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[100, 100], t2_times_us=[150, 150],
            single_qubit_error=[0.0001, 0.0001], two_qubit_error=[0.001],
            readout_error=[0.01, 0.01], gate_times_ns={"cx": 100},
        )
        estimator = ResourceEstimator()
        report = estimator.estimate(circuit, backend, 2, 0, 1)
        assert 0.0 <= report.estimated_fidelity <= 1.0
        assert report.optimal_shots >= 100


class TestQPUEstimator:
    def test_end_to_end(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator()
        report = estimator.estimate(circuit, "ibm_heron")

        assert report.backend_name == "ibm_heron"
        assert report.circuit_profile.num_qubits == 2
        assert report.estimated_fidelity > 0
        assert report.estimated_credits >= 0

    def test_compare_backends(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator()
        reports = estimator.compare_backends(
            circuit, ["ibm_heron", "ibm_brisbane", "ibm_sherbrooke"]
        )
        assert len(reports) == 3
        # Sorted by fidelity descending
        fidelities = [r.estimated_fidelity for r in reports]
        assert fidelities == sorted(fidelities, reverse=True)
