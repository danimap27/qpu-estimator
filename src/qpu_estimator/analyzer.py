"""Circuit analyzer: extract structural properties from QuantumCircuit."""

from qiskit import QuantumCircuit
from qiskit.circuit.library.standard_gates import CXGate, CZGate, ECRGate

from .models import CircuitProfile


class CircuitAnalyzer:
    """Analyze a quantum circuit and produce a CircuitProfile."""

    def analyze(self, circuit: QuantumCircuit) -> CircuitProfile:
        """Return structural profile of *circuit*."""
        num_qubits = circuit.num_qubits
        total_gates = 0
        single_qubit_gates = 0
        two_qubit_gates = 0
        measurement_ops = 0
        parameterized_gates = 0

        for instruction in circuit.data:
            op = instruction.operation
            total_gates += 1

            if op.name == "measure":
                measurement_ops += 1
                continue

            if op.name == "barrier":
                continue

            if self._is_two_qubit_gate(op):
                two_qubit_gates += 1
            else:
                single_qubit_gates += 1

            if self._is_parameterized(op):
                parameterized_gates += 1

        depth = circuit.depth()

        return CircuitProfile(
            num_qubits=num_qubits,
            total_gates=total_gates,
            single_qubit_gates=single_qubit_gates,
            two_qubit_gates=two_qubit_gates,
            depth=depth,
            measurement_ops=measurement_ops,
            parameterized_gates=parameterized_gates,
        )

    @staticmethod
    def _is_two_qubit_gate(op) -> bool:
        return isinstance(op, (CXGate, CZGate, ECRGate)) or op.num_qubits == 2

    @staticmethod
    def _is_parameterized(op) -> bool:
        """Check if a gate has free parameters (e.g. RX(theta))."""
        return hasattr(op, "params") and any(
            not isinstance(p, (int, float)) for p in op.params
        )
