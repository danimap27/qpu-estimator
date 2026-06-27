"""Plugin system for custom backends."""

from abc import ABC, abstractmethod
from typing import Any

from .models import BackendProfile


class BackendPlugin(ABC):
    """Base class for custom backend plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        ...

    @abstractmethod
    def get_profile(self) -> BackendProfile:
        """Return backend profile."""
        ...


class PluginRegistry:
    """Registry for backend plugins."""

    def __init__(self):
        self._plugins: dict[str, BackendPlugin] = {}

    def register(self, plugin: BackendPlugin) -> None:
        """Register a backend plugin."""
        self._plugins[plugin.name] = plugin

    def get_profile(self, name: str) -> BackendProfile:
        """Get profile from registered plugin."""
        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not registered. Available: {list(self._plugins.keys())}")
        return self._plugins[name].get_profile()

    def list_plugins(self) -> list[str]:
        """List registered plugin names."""
        return list(self._plugins.keys())


# Example: IonQ plugin
class IonQPlugin(BackendPlugin):
    """Example plugin for IonQ backend."""

    @property
    def name(self) -> str:
        return "ionq_harmony"

    def get_profile(self) -> BackendProfile:
        return BackendProfile(
            name=self.name,
            num_qubits=11,
            basis_gates=["gpi", "gpi2", "ms"],
            coupling_map=[[i, j] for i in range(11) for j in range(i + 1, 11)],
            t1_times_us=[10_000.0] * 11,
            t2_times_us=[10_000.0] * 11,
            single_qubit_error=[0.0001] * 11,
            two_qubit_error=[0.003] * 55,
            readout_error=[0.005] * 11,
            gate_times_ns={"gpi": 100.0, "gpi2": 100.0, "ms": 500.0},
        )
