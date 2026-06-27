"""Main orchestrator: QPUEstimator."""

from qiskit import QuantumCircuit

from .analyzer import CircuitAnalyzer
from .profiler import BackendProfiler
from .transpiler import TranspilationEstimator
from .estimator import ResourceEstimator, EstimationConfig
from .models import EstimationReport


class QPUEstimator:
    """
    End-to-end estimator for IBM Quantum hardware resource usage.

    Example::

        from qiskit import QuantumCircuit
        from qpu_estimator import QPUEstimator

        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()

        estimator = QPUEstimator()
        report = estimator.estimate(circuit, backend_name="ibm_heron")
        print(report)
    """

    def __init__(self, config: EstimationConfig | None = None):
        self.analyzer = CircuitAnalyzer()
        self.profiler = BackendProfiler()
        self.transpiler = TranspilationEstimator()
        self.resource_estimator = ResourceEstimator(config)

    def estimate(
        self, circuit: QuantumCircuit, backend_name: str
    ) -> EstimationReport:
        """Estimate resources for *circuit* on *backend_name*."""
        # Step 1: analyze circuit structure
        circuit_profile = self.analyzer.analyze(circuit)

        # Step 2: fetch backend profile
        backend_profile = self.profiler.get_profile(backend_name)

        # Step 3: estimate transpilation overhead
        swap_count, transpiled_depth, new_two_qubit = self.transpiler.estimate(
            circuit_profile, backend_profile
        )

        # Step 4: estimate resources
        report = self.resource_estimator.estimate(
            circuit_profile,
            backend_profile,
            transpiled_depth,
            swap_count,
            new_two_qubit,
        )

        return report

    def compare_backends(
        self, circuit: QuantumCircuit, backend_names: list[str]
    ) -> list[EstimationReport]:
        """Estimate resources across multiple backends and return sorted by fidelity."""
        reports = [self.estimate(circuit, name) for name in backend_names]
        return sorted(reports, key=lambda r: r.estimated_fidelity, reverse=True)
