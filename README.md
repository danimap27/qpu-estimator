# QPU-Estimator

A Python framework for estimating IBM Quantum hardware resource usage from arbitrary quantum circuits. Given a `QuantumCircuit` and a target IBM backend, it predicts execution time, optimal shot counts, accumulated error, and credit cost.

## Why

IBM Quantum Runtime provides execution APIs but no upfront resource estimator. For QML research—where you need to justify backend choice, compare transpilation overhead, or budget experiments across multiple backends—this framework fills the gap.

## Architecture

```
qpu_estimator/
├── analyzer/          # Circuit analysis (gate counts, depth, entanglement)
├── profiler/          # Backend profiling (T1/T2, gate errors, topology)
├── transpiler/        # Transpilation overhead estimation
├── estimator/         # Resource estimation (time, shots, fidelity, credits)
└── cli.py             # Command-line interface
```

## Quick Start

```python
from qiskit import QuantumCircuit
from qpu_estimator import QPUEstimator

circuit = QuantumCircuit(2)
circuit.h(0)
circuit.cx(0, 1)
circuit.measure_all()

estimator = QPUEstimator()
report = estimator.estimate(circuit, backend_name="ibm_heron")

print(report.execution_time_ms)   # ~0.5
print(report.optimal_shots)       # ~1024
print(report.estimated_fidelity)  # ~0.92
print(report.estimated_credits)   # ~1.2
```

## CLI

```bash
qpu-estimate circuit.qpy --backend ibm_heron --shots 1024
```

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## License

MIT
