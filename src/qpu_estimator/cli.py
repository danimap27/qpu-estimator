"""Command-line interface for QPU-Estimator."""

import argparse
import json
import sys

from qiskit import QuantumCircuit
from qiskit.qpy import load

from .orchestrator import QPUEstimator


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="qpu-estimate",
        description="Estimate IBM Quantum hardware resource usage from a circuit.",
    )
    parser.add_argument("circuit", help="Path to QPY file or Python file exporting 'circuit'")
    parser.add_argument(
        "--backend",
        default="ibm_heron",
        help="Target IBM backend name (default: ibm_heron)",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=None,
        help="Override optimal shot count",
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        help="Compare multiple backends",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable report",
    )

    args = parser.parse_args()

    # Load circuit
    if args.circuit.endswith(".qpy"):
        with open(args.circuit, "rb") as f:
            circuit = load(f)
    else:
        # Assume Python file with a 'circuit' variable
        import importlib.util

        spec = importlib.util.spec_from_file_location("circuit_module", args.circuit)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        circuit = module.circuit

    estimator = QPUEstimator()

    if args.compare:
        reports = estimator.compare_backends(circuit, args.compare)
    else:
        reports = [estimator.estimate(circuit, args.backend)]

    for report in reports:
        if args.json:
            print(json.dumps(_report_to_dict(report), indent=2))
        else:
            _print_report(report)

    return 0


def _report_to_dict(report):
    return {
        "backend": report.backend_name,
        "circuit": {
            "qubits": report.circuit_profile.num_qubits,
            "total_gates": report.circuit_profile.total_gates,
            "single_qubit_gates": report.circuit_profile.single_qubit_gates,
            "two_qubit_gates": report.circuit_profile.two_qubit_gates,
            "depth": report.circuit_profile.depth,
            "measurements": report.circuit_profile.measurement_ops,
        },
        "transpiled_depth": report.transpiled_depth,
        "execution_time_ms": report.estimated_execution_time_ms,
        "optimal_shots": report.optimal_shots,
        "estimated_fidelity": report.estimated_fidelity,
        "estimated_credits": report.estimated_credits,
        "swap_count": report.swap_count,
        "notes": report.notes,
    }


def _print_report(report):
    print(f"\n{'=' * 50}")
    print(f"Backend: {report.backend_name}")
    print(f"{'=' * 50}")
    print(f"Circuit qubits:        {report.circuit_profile.num_qubits}")
    print(f"Total gates:           {report.circuit_profile.total_gates}")
    print(f"Single-qubit gates:    {report.circuit_profile.single_qubit_gates}")
    print(f"Two-qubit gates:       {report.circuit_profile.two_qubit_gates}")
    print(f"Original depth:        {report.circuit_profile.depth}")
    print(f"Transpiled depth:      {report.transpiled_depth}")
    print(f"SWAP count:            {report.swap_count}")
    print(f"Execution time:        {report.estimated_execution_time_ms:.3f} ms")
    print(f"Optimal shots:         {report.optimal_shots}")
    print(f"Estimated fidelity:    {report.estimated_fidelity:.4f}")
    print(f"Estimated credits:     {report.estimated_credits:.4f}")
    if report.notes:
        print(f"\nNotes:")
        for note in report.notes:
            print(f"  - {note}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    sys.exit(main())
