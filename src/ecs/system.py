"""System base class plus the ordered pipeline that drives them."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from src.ecs.world import World


class System:
    """Unit of per-frame logic operating over entities in a World.

    Subclasses override :meth:`update` (variable dt) and/or
    :meth:`fixed_update` (deterministic step) and optionally :meth:`render`.
    """

    def __init__(self, name: str | None = None, priority: int = 0) -> None:
        self.name: str = name or type(self).__name__
        self.priority: int = priority  # lower runs first
        self.enabled: bool = True

    def on_register(self, world: "World") -> None:
        """Hook invoked once when added to *world*."""

    def update(self, world: "World", dt: float) -> None:
        """Variable-timestep tick."""

    def fixed_update(self, world: "World", dt: float) -> None:
        """Deterministic physics-rate tick."""

    def render(self, world: "World") -> None:
        """Draw pass executed after all updates."""

    def __repr__(self) -> str:
        return f"<System {self.name} priority={self.priority}>"


class SystemManager:
    """Registry keeping systems sorted by priority for each phase."""

    def __init__(self) -> None:
        self._systems: List[System] = []
        self._dirty: bool = False

    def register(self, system: System, world: Optional["World"] = None) -> System:
        """Add *system* unless already present; fires its on_register hook."""
        if any(isinstance(s, type(system)) and s.name == system.name for s in self._systems):
            raise ValueError(f"system {system.name!r} already registered")
        self._systems.append(system)
        self._dirty = True
        if world is not None:
            system.on_register(world)
        return system

    def unregister(self, system_name: str) -> bool:
        """Remove the system called *system_name*; returns success."""
        before = len(self._systems)
        self._systems = [s for s in self._systems if s.name != system_name]
        return len(self._systems) != before

    @property
    def systems(self) -> List[System]:
        """Priority-sorted snapshot of registered systems."""
        if self._dirty:
            self._systems.sort(key=lambda s: s.priority)
            self._dirty = False
        return list(self._systems)

    def _run(self, world: "World", phase: str, dt: float = 0.0) -> int:
        count = 0
        for system in self.systems:
            if not system.enabled:
                continue
            getattr(system, phase)(world, dt) if phase != "render" else system.render(world)
            count += 1
        return count

    def update(self, world: "World", dt: float) -> int:
        """Run every enabled system's variable update; returns run count."""
        return self._run(world, "update", dt)

    def fixed_update(self, world: "World", dt: float) -> int:
        """Run deterministic fixed-step callbacks; returns run count."""
        return self._run(world, "fixed_update", dt)

    def render(self, world: "World") -> int:
        """Run every enabled render pass; returns run count."""
        return self._run(world, "render")

    def clear(self) -> None:
        """Detach every system."""
        self._systems.clear()
        self._dirty = True

    def __len__(self) -> int:
        return len(self._systems)

    def describe_pipeline(self) -> Tuple[str, ...]:
        """Ordered names of systems, useful for debugging frame order."""
        return tuple(s.name for s in self.systems)
