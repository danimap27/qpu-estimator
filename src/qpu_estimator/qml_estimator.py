"""QML-specific estimators for VQC, MAML/QMAML, and transfer learning."""

from dataclasses import dataclass

from qiskit import QuantumCircuit

from .orchestrator import QPUEstimator
from .models import EstimationReport


@dataclass
class VQCEstimationConfig:
    """Configuration for VQC resource estimation."""

    num_parameters: int
    num_training_epochs: int
    shots_per_evaluation: int | None = None  # None = use optimizer
    gradient_method: str = "spsa"  # spsa, parameter-shift, finite-diff
    num_gradient_evals_per_step: int = 2  # SPSA: 2, parameter-shift: 2*params


@dataclass
class MAMLEstimationConfig:
    """Configuration for MAML/QMAML resource estimation."""

    num_tasks: int
    inner_loop_steps: int
    outer_loop_steps: int
    shots_per_inner_eval: int | None = None
    shots_per_outer_eval: int | None = None
    meta_parameters: int = 0  # number of meta-parameters


@dataclass
class TransferLearningConfig:
    """Configuration for quantum transfer learning estimation."""

    classical_layers: int
    quantum_layers: int
    frozen_classical: bool = True
    fine_tune_epochs: int = 10


class QMLEstimator:
    """
    Estimate resources for QML workloads.

    Covers:
    - VQC training loops
    - MAML/QMAML meta-learning
    - Quantum transfer learning
    """

    def __init__(self, base_estimator: QPUEstimator | None = None):
        self.base_estimator = base_estimator or QPUEstimator()

    def estimate_vqc_training(
        self,
        circuit: QuantumCircuit,
        backend_name: str,
        config: VQCEstimationConfig,
    ) -> EstimationReport:
        """
        Estimate total resources for VQC training.

        Total cost = epochs * (forward + backward passes).
        """
        # Single evaluation
        single_report = self.base_estimator.estimate(circuit, backend_name)

        # Gradient evaluations per epoch
        if config.gradient_method == "spsa":
            grad_evals = config.num_gradient_evals_per_step
        elif config.gradient_method == "parameter-shift":
            grad_evals = 2 * config.num_parameters
        else:
            grad_evals = config.num_gradient_evals_per_step

        # Total evaluations per epoch: forward + backward
        evals_per_epoch = 1 + grad_evals

        # Total shots
        shots_per_eval = config.shots_per_evaluation or single_report.optimal_shots
        total_shots = shots_per_eval * evals_per_epoch * config.num_training_epochs

        # Total time
        total_time_ms = (
            single_report.estimated_execution_time_ms
            * evals_per_epoch
            * config.num_training_epochs
        )

        # Total credits
        total_credits = single_report.estimated_credits * evals_per_epoch * config.num_training_epochs

        # Fidelity degrades with repeated evaluations (accumulated noise)
        fidelity = single_report.estimated_fidelity ** evals_per_epoch

        notes = single_report.notes + [
            f"VQC training: {config.num_training_epochs} epochs",
            f"Gradient method: {config.gradient_method}",
            f"Gradient evals per step: {grad_evals}",
            f"Total evaluations: {evals_per_epoch * config.num_training_epochs}",
        ]

        return EstimationReport(
            backend_name=backend_name,
            circuit_profile=single_report.circuit_profile,
            transpiled_depth=single_report.transpiled_depth,
            estimated_execution_time_ms=total_time_ms,
            optimal_shots=total_shots,
            estimated_fidelity=fidelity,
            estimated_credits=total_credits,
            swap_count=single_report.swap_count,
            notes=notes,
        )

    def estimate_maml(
        self,
        circuit: QuantumCircuit,
        backend_name: str,
        config: MAMLEstimationConfig,
    ) -> EstimationReport:
        """
        Estimate resources for MAML/QMAML training.

        Total cost = outer_steps * tasks * (inner_evals + outer_evals).
        """
        single_report = self.base_estimator.estimate(circuit, backend_name)

        # Inner loop: adaptation per task
        inner_shots = config.shots_per_inner_eval or single_report.optimal_shots
        inner_evals = config.inner_loop_steps

        # Outer loop: meta-update across tasks
        outer_shots = config.shots_per_outer_eval or single_report.optimal_shots
        outer_evals = 1  # meta-gradient evaluation

        # Total per outer step
        total_evals_per_outer = config.num_tasks * (inner_evals + outer_evals)
        total_shots_per_outer = config.num_tasks * (
            inner_shots * inner_evals + outer_shots * outer_evals
        )

        # Grand total
        total_evals = total_evals_per_outer * config.outer_loop_steps
        total_shots = total_shots_per_outer * config.outer_loop_steps
        total_time_ms = (
            single_report.estimated_execution_time_ms * total_evals
        )
        total_credits = single_report.estimated_credits * total_evals

        # Fidelity degrades with inner loop steps
        fidelity = single_report.estimated_fidelity ** inner_evals

        notes = single_report.notes + [
            f"MAML: {config.num_tasks} tasks, {config.inner_loop_steps} inner steps",
            f"Outer loop: {config.outer_loop_steps} steps",
            f"Total evaluations: {total_evals}",
        ]

        return EstimationReport(
            backend_name=backend_name,
            circuit_profile=single_report.circuit_profile,
            transpiled_depth=single_report.transpiled_depth,
            estimated_execution_time_ms=total_time_ms,
            optimal_shots=total_shots,
            estimated_fidelity=fidelity,
            estimated_credits=total_credits,
            swap_count=single_report.swap_count,
            notes=notes,
        )

    def estimate_transfer_learning(
        self,
        quantum_circuit: QuantumCircuit,
        backend_name: str,
        config: TransferLearningConfig,
    ) -> EstimationReport:
        """
        Estimate resources for quantum transfer learning.

        Cost = classical pre-training (ignored) + quantum fine-tuning.
        """
        single_report = self.base_estimator.estimate(quantum_circuit, backend_name)

        # Quantum fine-tuning epochs
        total_evals = config.fine_tune_epochs
        total_shots = single_report.optimal_shots * total_evals
        total_time_ms = single_report.estimated_execution_time_ms * total_evals
        total_credits = single_report.estimated_credits * total_evals

        notes = single_report.notes + [
            f"Transfer learning: {config.fine_tune_epochs} fine-tune epochs",
            f"Classical layers: {config.classical_layers}, Quantum layers: {config.quantum_layers}",
            f"Frozen classical: {config.frozen_classical}",
        ]

        return EstimationReport(
            backend_name=backend_name,
            circuit_profile=single_report.circuit_profile,
            transpiled_depth=single_report.transpiled_depth,
            estimated_execution_time_ms=total_time_ms,
            optimal_shots=total_shots,
            estimated_fidelity=single_report.estimated_fidelity,
            estimated_credits=total_credits,
            swap_count=single_report.swap_count,
            notes=notes,
        )
