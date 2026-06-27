"""Training time estimator for QML workloads.

Estimates total wall-clock time including:
- Forward/backward passes per batch
- Quantum evaluation time (from QPU-Estimator)
- Classical overhead (data loading, optimizer steps)
- Communication overhead (API calls to IBM)
- Queue time (heuristic based on plan priority)
"""

from dataclasses import dataclass
from typing import Optional

from qiskit import QuantumCircuit

from .orchestrator import QPUEstimator
from .models import EstimationReport


@dataclass
class TrainingTimeConfig:
    """Configuration for training time estimation."""

    # Dataset
    n_samples: int
    batch_size: int
    n_epochs: int

    # Quantum
    shots_per_eval: int
    circuit_eval_time_ms: float  # from QPUEstimator

    # Classical overhead (empirical defaults)
    data_loading_time_ms: float = 5.0  # per batch
    optimizer_step_time_ms: float = 1.0  # per step
    classical_forward_time_ms: float = 2.0  # per batch

    # Communication overhead (IBM Runtime)
    api_call_overhead_ms: float = 50.0  # per circuit submission
    result_fetch_overhead_ms: float = 20.0  # per result retrieval

    # Queue time (heuristic based on plan)
    plan_priority: str = "open"  # open, paygo, premium
    circuits_per_job: int = 1  # batch multiple circuits per job

    # Gradient method
    gradient_method: str = "spsa"  # spsa, parameter-shift, finite-diff
    n_params: int = 0  # for parameter-shift: 2*n_params evals


class TrainingTimeEstimator:
    """
    Estimate total wall-clock training time for QML experiments.

    Combines quantum execution time with classical overhead
    and queue time heuristics.
    """

    # Queue time heuristics (empirical, in minutes per job)
    _QUEUE_TIME_MINUTES = {
        "open": 30.0,      # 30 min average for open plan
        "paygo": 5.0,      # 5 min for pay-as-you-go
        "premium": 1.0,    # 1 min for premium
    }

    def __init__(self, base_estimator: Optional[QPUEstimator] = None):
        self.base_estimator = base_estimator or QPUEstimator()

    def estimate_training_time(
        self,
        circuit: QuantumCircuit,
        backend_name: str,
        config: TrainingTimeConfig,
    ) -> dict:
        """
        Estimate total training time breakdown.

        Returns dict with time components and recommendations.
        """
        n_batches = (config.n_samples + config.batch_size - 1) // config.batch_size

        # Quantum evals per batch
        if config.gradient_method == "spsa":
            quantum_evals_per_batch = 3  # forward + 2 SPSA evals
        elif config.gradient_method == "parameter-shift":
            quantum_evals_per_batch = 1 + 2 * config.n_params
        else:
            quantum_evals_per_batch = 3

        # Time per quantum eval (execution only, no queue)
        time_per_quantum_eval_ms = config.circuit_eval_time_ms

        # API overhead per eval
        api_overhead_ms = config.api_call_overhead_ms + config.result_fetch_overhead_ms

        # Per batch breakdown
        quantum_exec_time_per_batch = quantum_evals_per_batch * time_per_quantum_eval_ms
        api_time_per_batch = quantum_evals_per_batch * api_overhead_ms
        classical_time_per_batch = (
            config.data_loading_time_ms +
            config.classical_forward_time_ms +
            config.optimizer_step_time_ms
        )
        
        # Total per batch (execution only)
        total_exec_per_batch = quantum_exec_time_per_batch + api_time_per_batch + classical_time_per_batch

        # Per epoch
        time_per_epoch_ms = n_batches * total_exec_per_batch

        # Total execution time (no queue)
        total_exec_time_ms = config.n_epochs * time_per_epoch_ms

        # Queue time: one queue per batch for open plan, or batched
        queue_time_per_batch_ms = self._estimate_queue_time(config) * 60 * 1000
        
        # If using batching (multiple circuits per job), amortize queue time
        if config.circuits_per_job > 1:
            queue_time_per_batch_ms /= config.circuits_per_job
        
        total_queue_time_ms = n_batches * config.n_epochs * queue_time_per_batch_ms

        # Grand total
        total_wall_clock_ms = total_exec_time_ms + total_queue_time_ms

        return {
            "total_time_ms": total_wall_clock_ms,
            "total_time_min": total_wall_clock_ms / 60000,
            "total_time_hours": total_wall_clock_ms / 3600000,
            "total_time_days": total_wall_clock_ms / 86400000,
            "quantum_exec_time_ms": total_exec_time_ms * (quantum_exec_time_per_batch / total_exec_per_batch),
            "api_overhead_time_ms": total_exec_time_ms * (api_time_per_batch / total_exec_per_batch),
            "classical_time_ms": total_exec_time_ms * (classical_time_per_batch / total_exec_per_batch),
            "queue_time_ms": total_queue_time_ms,
            "per_epoch_time_ms": time_per_epoch_ms + (n_batches * queue_time_per_batch_ms),
            "per_batch_time_ms": total_exec_per_batch + queue_time_per_batch_ms,
            "n_batches": n_batches,
            "quantum_evals_per_batch": quantum_evals_per_batch,
            "breakdown": {
                "quantum_exec_per_batch_ms": quantum_exec_time_per_batch,
                "api_overhead_per_batch_ms": api_time_per_batch,
                "classical_overhead_per_batch_ms": classical_time_per_batch,
                "queue_per_batch_ms": queue_time_per_batch_ms,
            },
            "recommendations": self._generate_recommendations(
                total_wall_clock_ms, total_queue_time_ms, config
            ),
        }

    def _generate_recommendations(self, total_ms: float, queue_ms: float, config: TrainingTimeConfig) -> list:
        """Generate optimization recommendations."""
        recs = []
        
        if queue_ms / total_ms > 0.5:
            recs.append(f"Queue time dominates ({queue_ms/total_ms*100:.0f}%). Consider: pay-as-you-go plan, larger batches, or session mode.")
        
        if config.plan_priority == "open" and total_ms > 3600000:  # > 1 hour
            recs.append("Open plan queue times are high. For experiments >1 hour, consider IBM pay-as-you-go or premium plan.")
        
        if config.n_samples / config.batch_size > 100:
            recs.append(f"Large number of batches ({(config.n_samples + config.batch_size - 1) // config.batch_size}). Consider increasing batch size to reduce API calls.")
        
        if config.gradient_method == "parameter-shift" and config.n_params > 10:
            recs.append(f"Parameter-shift with {config.n_params} params requires {1 + 2*config.n_params} evals/batch. Consider SPSA (2 evals/batch) for hardware.")
        
        if not recs:
            recs.append("Configuration looks reasonable for the chosen plan.")
        
        return recs

    def estimate_with_session(
        self,
        circuit: QuantumCircuit,
        backend_name: str,
        n_samples: int,
        batch_size: int,
        n_epochs: int,
        gradient_method: str = "spsa",
        n_params: int = 0,
        plan_priority: str = "open",
    ) -> dict:
        """
        Estimate training time using IBM Runtime Session mode.
        
        Session mode queues once and runs all circuits in a single session,
        dramatically reducing queue time for training workloads.
        """
        # Get base estimate
        base = self.estimate_full_experiment(
            circuit, backend_name, n_samples, batch_size, n_epochs,
            gradient_method, n_params, plan_priority,
        )
        
        # In session mode: queue once, not per batch
        n_batches = (n_samples + batch_size - 1) // batch_size
        total_evals = n_batches * n_epochs * base["quantum_evals_per_batch"]
        
        # Single queue at start
        session_queue_time_ms = self._QUEUE_TIME_MINUTES.get(plan_priority, 30.0) * 60 * 1000
        
        # Total time = queue once + all executions
        total_time_ms = session_queue_time_ms + base["quantum_exec_time_ms"] + base["classical_time_ms"] + base["api_overhead_time_ms"]
        
        return {
            **base,
            "mode": "session",
            "total_time_ms": total_time_ms,
            "total_time_min": total_time_ms / 60000,
            "total_time_hours": total_time_ms / 3600000,
            "total_time_days": total_time_ms / 86400000,
            "queue_time_ms": session_queue_time_ms,
            "speedup_vs_standard": base["total_time_ms"] / total_time_ms if total_time_ms > 0 else 1.0,
            "recommendations": [
                "Session mode: single queue, all circuits in one job.",
                f"Speedup vs standard: {base['total_time_ms'] / total_time_ms:.1f}x" if total_time_ms > 0 else "N/A",
                "Use for training workloads with many circuit evaluations.",
            ],
        }

    def estimate_full_experiment(
        self,
        circuit: QuantumCircuit,
        backend_name: str,
        n_samples: int,
        batch_size: int,
        n_epochs: int,
        gradient_method: str = "spsa",
        n_params: int = 0,
        plan_priority: str = "open",
    ) -> dict:
        """
        High-level API: estimate full experiment time from circuit and training config.
        """
        # Get quantum execution time from QPU-Estimator
        report = self.base_estimator.estimate(circuit, backend_name)

        config = TrainingTimeConfig(
            n_samples=n_samples,
            batch_size=batch_size,
            n_epochs=n_epochs,
            shots_per_eval=report.optimal_shots,
            circuit_eval_time_ms=report.estimated_execution_time_ms,
            gradient_method=gradient_method,
            n_params=n_params,
            plan_priority=plan_priority,
        )

        time_estimate = self.estimate_training_time(circuit, backend_name, config)

        return {
            "backend": backend_name,
            "circuit_depth": report.circuit_profile.depth,
            "transpiled_depth": report.transpiled_depth,
            "estimated_fidelity": report.estimated_fidelity,
            "optimal_shots": report.optimal_shots,
            **time_estimate,
        }

    @classmethod
    def _estimate_queue_time(cls, config: TrainingTimeConfig) -> float:
        """Estimate queue time in minutes based on plan priority."""
        return cls._QUEUE_TIME_MINUTES.get(config.plan_priority, 30.0)
