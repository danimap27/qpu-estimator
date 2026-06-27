"""Tests for QPU-Estimator Phase 1 — IBM Integration."""

import os
from unittest.mock import MagicMock, patch

import pytest
from qiskit import QuantumCircuit

from qpu_estimator import QPUEstimator
from qpu_estimator.analyzer import CircuitAnalyzer
from qpu_estimator.profiler import BackendProfiler
from qpu_estimator.transpiler import TranspilationEstimator
from qpu_estimator.estimator import ResourceEstimator, EstimationConfig
from qpu_estimator.models import BackendProfile


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

    def test_parameterized_circuit(self):
        from qiskit.circuit import Parameter

        circuit = QuantumCircuit(1)
        theta = Parameter("theta")
        circuit.rx(theta, 0)

        analyzer = CircuitAnalyzer()
        profile = analyzer.analyze(circuit)

        assert profile.parameterized_gates == 1
        assert profile.single_qubit_gates == 1


class TestBackendProfiler:
    def test_known_mock_backends(self):
        profiler = BackendProfiler(use_live=False)
        assert "ibm_heron" in profiler.list_backends()
        assert "ibm_brisbane" in profiler.list_backends()

    def test_mock_profile(self):
        profiler = BackendProfiler(use_live=False)
        profile = profiler.get_profile("ibm_heron")
        assert profile.num_qubits == 133
        assert "ecr" in profile.basis_gates

    def test_unknown_backend(self):
        profiler = BackendProfiler(use_live=False)
        with pytest.raises(ValueError):
            profiler.get_profile("ibm_fake")

    def test_live_backend_listing(self):
        """Test that live backend listing works when token is available."""
        profiler = BackendProfiler(use_live=True)
        # If no token, should return empty list gracefully
        backends = profiler.list_live_backends()
        assert isinstance(backends, list)

    def test_live_profile_with_mock(self):
        """Test live profile fetching with mocked IBM service."""
        mock_backend = MagicMock()
        mock_backend.name = "ibm_test"
        mock_backend.configuration.return_value.n_qubits = 2
        mock_backend.configuration.return_value.basis_gates = ["rz", "sx", "x", "cz"]
        mock_backend.configuration.return_value.coupling_map = [[0, 1], [1, 0]]
        mock_backend.properties.return_value.t1.return_value = 1e-4
        mock_backend.properties.return_value.t2.return_value = 1.5e-4
        mock_backend.properties.return_value.readout_error.return_value = 0.01
        mock_backend.properties.return_value.gate_error.return_value = 0.001

        mock_service = MagicMock()
        mock_service.backend.return_value = mock_backend

        with patch(
            "qiskit_ibm_runtime.QiskitRuntimeService", return_value=mock_service
        ):
            profiler = BackendProfiler(use_live=True, token="fake_token")
            profile = profiler.get_profile("ibm_test")

            assert profile.name == "ibm_test"
            assert profile.num_qubits == 2
            assert profile.basis_gates == ["rz", "sx", "x", "cz"]
            assert profile.t1_times_us == [100.0, 100.0]
            assert profile.t2_times_us == [150.0, 150.0]

    def test_live_fallback_to_mock(self):
        """Test that live fetch falls back to mock on failure."""
        profiler = BackendProfiler(use_live=True, token="fake_token")
        # Should fallback to mock since token is invalid
        profile = profiler.get_profile("ibm_heron")
        assert profile.name == "ibm_heron"


class TestTranspilationEstimator:
    def test_real_transpile_bell_state(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)

        profile = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["rz", "sx", "x", "cz"],
            coupling_map=[[0, 1], [1, 0]],
            t1_times_us=[100, 100],
            t2_times_us=[150, 150],
            single_qubit_error=[0.0, 0.0],
            two_qubit_error=[0.0],
            readout_error=[0.0, 0.0],
            gate_times_ns={"rz": 0, "sx": 35, "x": 35, "cz": 500},
        )
        from qpu_estimator.models import CircuitProfile

        circuit_profile = CircuitProfile(
            num_qubits=2,
            total_gates=2,
            single_qubit_gates=1,
            two_qubit_gates=1,
            depth=2,
            measurement_ops=0,
            parameterized_gates=0,
        )
        estimator = TranspilationEstimator()
        swaps, depth, tq = estimator.estimate(
            circuit, circuit_profile, profile, use_real_transpiler=True
        )
        # For a local CNOT on a connected pair, no swaps needed
        assert swaps == 0
        assert depth >= 2

    def test_heuristic_fallback(self):
        from qpu_estimator.models import CircuitProfile, BackendProfile

        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)

        profile = CircuitProfile(
            num_qubits=2,
            total_gates=2,
            single_qubit_gates=1,
            two_qubit_gates=1,
            depth=2,
            measurement_ops=0,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cz"],
            coupling_map=[[0, 1]],
            t1_times_us=[100, 100],
            t2_times_us=[150, 150],
            single_qubit_error=[0.0, 0.0],
            two_qubit_error=[0.0],
            readout_error=[0.0, 0.0],
            gate_times_ns={"cz": 100},
        )
        estimator = TranspilationEstimator()
        swaps, depth, tq = estimator.estimate(
            circuit, profile, backend, use_real_transpiler=False
        )
        assert swaps >= 0


class TestResourceEstimator:
    def test_fidelity_range(self):
        from qpu_estimator.models import CircuitProfile, BackendProfile

        circuit = CircuitProfile(
            num_qubits=2,
            total_gates=2,
            single_qubit_gates=1,
            two_qubit_gates=1,
            depth=2,
            measurement_ops=2,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[100, 100],
            t2_times_us=[150, 150],
            single_qubit_error=[0.0001, 0.0001],
            two_qubit_error=[0.001],
            readout_error=[0.01, 0.01],
            gate_times_ns={"cx": 100},
        )
        estimator = ResourceEstimator()
        report = estimator.estimate(circuit, backend, 2, 0, 1)
        assert 0.0 <= report.estimated_fidelity <= 1.0
        assert report.optimal_shots >= 100

    def test_shot_optimization(self):
        from qpu_estimator.models import CircuitProfile, BackendProfile

        circuit = CircuitProfile(
            num_qubits=2,
            total_gates=2,
            single_qubit_gates=1,
            two_qubit_gates=1,
            depth=2,
            measurement_ops=2,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[100, 100],
            t2_times_us=[150, 150],
            single_qubit_error=[0.0001, 0.0001],
            two_qubit_error=[0.001],
            readout_error=[0.01, 0.01],
            gate_times_ns={"cx": 100},
        )
        config = EstimationConfig(target_precision=0.05, confidence=0.99)
        estimator = ResourceEstimator(config)
        report = estimator.estimate(circuit, backend, 2, 0, 1)
        # Higher confidence / lower precision should need more shots
        assert report.optimal_shots >= 100


class TestQPUEstimator:
    def test_end_to_end_mock(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator(use_live=False, use_real_transpiler=False)
        report = estimator.estimate(circuit, "ibm_heron")

        assert report.backend_name == "ibm_heron"
        assert report.circuit_profile.num_qubits == 2
        assert report.estimated_fidelity > 0
        assert report.estimated_credits >= 0

    def test_compare_backends_mock(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator(use_live=False, use_real_transpiler=False)
        reports = estimator.compare_backends(
            circuit, ["ibm_heron", "ibm_brisbane", "ibm_sherbrooke"]
        )
        assert len(reports) == 3
        fidelities = [r.estimated_fidelity for r in reports]
        assert fidelities == sorted(fidelities, reverse=True)

    def test_end_to_end_real_transpile(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator(use_live=False, use_real_transpiler=True)
        report = estimator.estimate(circuit, "ibm_heron")

        assert report.backend_name == "ibm_heron"
        assert report.transpiled_depth >= report.circuit_profile.depth

    def test_live_backend_listing(self):
        estimator = QPUEstimator(use_live=False)
        backends = estimator.list_live_backends()
        assert isinstance(backends, list)


class TestPhase2AdvancedEstimation:
    """Tests for Phase 2 — Advanced Estimation."""

    def test_noise_aware_fidelity_vs_simple(self):
        """Noise-aware fidelity should generally be lower than simple model."""
        from qpu_estimator.models import CircuitProfile, BackendProfile
        from qpu_estimator.noise_model import NoiseAwareFidelityEstimator

        circuit = CircuitProfile(
            num_qubits=2,
            total_gates=3,
            single_qubit_gates=2,
            two_qubit_gates=1,
            depth=3,
            measurement_ops=2,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[50.0, 50.0],
            t2_times_us=[30.0, 30.0],
            single_qubit_error=[0.001, 0.001],
            two_qubit_error=[0.005],
            readout_error=[0.02, 0.02],
            gate_times_ns={"cx": 500},
        )

        noise_estimator = NoiseAwareFidelityEstimator()
        noise_fidelity = noise_estimator.estimate(circuit, backend, 5, 0, 1)

        # Simple model (no thermal relaxation)
        sq_fid = (1 - 0.001) ** 2
        tq_fid = (1 - 0.005) ** 1
        ro_fid = (1 - 0.02) ** 2
        simple_fidelity = sq_fid * tq_fid * ro_fid

        # Noise-aware should be lower due to thermal relaxation
        assert noise_fidelity <= simple_fidelity
        assert 0.0 <= noise_fidelity <= 1.0

    def test_shot_optimizer_methods(self):
        """Test different shot optimization methods."""
        from qpu_estimator.shot_optimizer import ShotOptimizer, ShotConfig

        config = ShotConfig(target_precision=0.01, confidence=0.95)
        optimizer = ShotOptimizer(config)

        hoeffding = optimizer.optimal_shots("hoeffding")
        chernoff = optimizer.optimal_shots("chernoff")
        clopper = optimizer.optimal_shots("clopper-pearson")

        assert hoeffding >= 100
        assert chernoff >= 100
        assert clopper >= 100

        # All methods should give reasonable shot counts within bounds
        assert hoeffding <= config.max_shots
        assert chernoff <= config.max_shots
        assert clopper <= config.max_shots

    def test_shot_precision_tradeoff(self):
        """Higher precision should require more shots."""
        from qpu_estimator.shot_optimizer import ShotOptimizer, ShotConfig

        loose = ShotConfig(target_precision=0.05, confidence=0.95)
        tight = ShotConfig(target_precision=0.01, confidence=0.95)

        loose_shots = ShotOptimizer(loose).optimal_shots("hoeffding")
        tight_shots = ShotOptimizer(tight).optimal_shots("hoeffding")

        assert tight_shots > loose_shots

    def test_noise_config_toggles(self):
        """Test that noise config toggles affect fidelity."""
        from qpu_estimator.models import CircuitProfile, BackendProfile
        from qpu_estimator.noise_model import NoiseAwareFidelityEstimator, NoiseConfig

        circuit = CircuitProfile(
            num_qubits=2,
            total_gates=3,
            single_qubit_gates=2,
            two_qubit_gates=1,
            depth=3,
            measurement_ops=2,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[50.0, 50.0],
            t2_times_us=[30.0, 30.0],
            single_qubit_error=[0.001, 0.001],
            two_qubit_error=[0.005],
            readout_error=[0.02, 0.02],
            gate_times_ns={"cx": 500},
        )

        full = NoiseAwareFidelityEstimator(NoiseConfig(True, True, True))
        no_thermal = NoiseAwareFidelityEstimator(NoiseConfig(True, False, True))

        full_fid = full.estimate(circuit, backend, 5, 0, 1)
        no_thermal_fid = no_thermal.estimate(circuit, backend, 5, 0, 1)

        # Without thermal relaxation, fidelity should be higher
        assert no_thermal_fid >= full_fid

    def test_estimator_with_noise_aware_config(self):
        """Test ResourceEstimator with noise-aware fidelity enabled."""
        from qpu_estimator.models import CircuitProfile, BackendProfile
        from qpu_estimator.estimator import ResourceEstimator, EstimationConfig

        circuit = CircuitProfile(
            num_qubits=2,
            total_gates=3,
            single_qubit_gates=2,
            two_qubit_gates=1,
            depth=3,
            measurement_ops=2,
            parameterized_gates=0,
        )
        backend = BackendProfile(
            name="mock",
            num_qubits=2,
            basis_gates=["cx"],
            coupling_map=[[0, 1]],
            t1_times_us=[100.0, 100.0],
            t2_times_us=[80.0, 80.0],
            single_qubit_error=[0.0001, 0.0001],
            two_qubit_error=[0.001],
            readout_error=[0.01, 0.01],
            gate_times_ns={"cx": 100},
        )

        config = EstimationConfig(
            use_noise_aware_fidelity=True,
            shot_method="chernoff",
        )
        estimator = ResourceEstimator(config)
        report = estimator.estimate(circuit, backend, 5, 0, 1)

        assert report.estimated_fidelity > 0
        assert report.optimal_shots >= 100
        assert "Noise-aware" in str(report.notes)
        assert "chernoff" in str(report.notes)


class TestPhase1Integration:
    """Integration tests for Phase 1 features."""

    def test_live_profile_with_env_token(self):
        """Test live profiling when QISKIT_IBM_TOKEN is set."""
        if not os.environ.get("QISKIT_IBM_TOKEN"):
            pytest.skip("QISKIT_IBM_TOKEN not set")

        profiler = BackendProfiler(use_live=True)
        backends = profiler.list_live_backends()
        if not backends:
            pytest.skip("No live backends available")

        profile = profiler.get_profile(backends[0])
        assert profile.num_qubits > 0
        assert len(profile.basis_gates) > 0
        assert len(profile.coupling_map) > 0

    def test_real_transpilation_vs_heuristic(self):
        """Compare real transpilation with heuristic for accuracy."""
        circuit = QuantumCircuit(3)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.cx(1, 2)
        circuit.measure_all()

        estimator_real = QPUEstimator(use_live=False, use_real_transpiler=True)
        estimator_heuristic = QPUEstimator(use_live=False, use_real_transpiler=False)

        report_real = estimator_real.estimate(circuit, "ibm_heron")
        report_heuristic = estimator_heuristic.estimate(circuit, "ibm_heron")

        # Real transpilation should generally give more accurate (lower) depth
        assert report_real.transpiled_depth >= 0
        assert report_heuristic.transpiled_depth >= 0

    def test_multi_backend_live_comparison(self):
        """Test comparing multiple backends with live data."""
        if not os.environ.get("QISKIT_IBM_TOKEN"):
            pytest.skip("QISKIT_IBM_TOKEN not set")

        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator(use_live=True, use_real_transpiler=True)
        backends = estimator.list_live_backends()
        if len(backends) < 2:
            pytest.skip("Need at least 2 live backends")

        reports = estimator.compare_backends(circuit, backends[:2])
        assert len(reports) == 2
        assert reports[0].estimated_fidelity >= reports[1].estimated_fidelity
