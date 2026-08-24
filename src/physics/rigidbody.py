"""Newtonian rigid bodies: mass, forces, damping, and integration."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from src.math.vector import Vector2


@dataclass
class ForceAccumulator:
    """Collects forces and impulses applied between integration steps."""

    force: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    impulse: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    torque: float = 0.0

    def reset(self) -> None:
        """Clear all accumulated effects after a solve."""
        self.force = Vector2(0.0, 0.0)
        self.impulse = Vector2(0.0, 0.0)
        self.torque = 0.0


class RigidBody:
    """A movable body with linear dynamics driven by the physics world."""

    GRAVITY: Vector2 = Vector2(0.0, -980.0)

    def __init__(self, position: Vector2 | None = None, mass: float = 1.0,
                 body_type: str = "dynamic") -> None:
        self.position: Vector2 = position or Vector2(0.0, 0.0)
        self.velocity: Vector2 = Vector2(0.0, 0.0)
        self.acceleration: Vector2 = Vector2(0.0, 0.0)
        self.angle_degrees: float = 0.0
        self.angular_velocity: float = 0.0
        self.body_type: str = body_type
        self.gravity_scale: float = 1.0
        self.linear_damping: float = 0.05
        self.restitution: float = 0.2
        self.friction: float = 0.5
        self.is_sensor: bool = False
        self.awake: bool = True
        self.sleep_timer: float = 0.0
        self.tag: Optional[str] = None
        self.accumulator: ForceAccumulator = ForceAccumulator()
        self._mass: float = max(1e-6, mass)

    @property
    def mass(self) -> float:
        """Inertial mass of the body."""
        return self._mass

    @mass.setter
    def mass(self, value: float) -> None:
        """Update mass, clamping to a tiny positive epsilon."""
        if value <= 0:
            raise ValueError("mass must be positive")
        self._mass = value

    @property
    def inverse_mass(self) -> float:
        """``1/mass``; zero for static bodies so they never move."""
        return 0.0 if self.body_type == "static" else 1.0 / self._mass

    def is_dynamic(self) -> bool:
        """True when gravity and collisions affect this body."""
        return self.body_type == "dynamic"

    # -- forces -----------------------------------------------------------------

    def apply_force(self, force: Vector2) -> None:
        """Add a continuous force consumed at the next integration."""
        if not self.is_dynamic():
            return
        self.accumulator.force = self.accumulator.force + force
        self.wake()

    def apply_impulse(self, impulse: Vector2) -> None:
        """Instantaneously change momentum by *impulse*."""
        if not self.is_dynamic():
            return
        self.velocity = self.velocity + impulse * self.inverse_mass
        self.wake()

    def apply_gravity(self, dt: float, gravity: Vector2 | None = None) -> None:
        """Fold gravity into velocity for this step."""
        if not self.is_dynamic():
            return
        g = gravity if gravity is not None else RigidBody.GRAVITY
        self.velocity = self.velocity + g * (self.gravity_scale * dt)

    def wake(self) -> None:
        """Mark the body active and reset its sleep timer."""
        self.awake = True
        self.sleep_timer = 0.0

    def try_sleep(self, threshold: float = 4.0, seconds: float = 0.6) -> bool:
        """Sleep the body once it stays slow long enough."""
        if not self.is_dynamic():
            return False
        if self.velocity.length() < threshold:
            self.sleep_timer += seconds
            if self.sleep_timer >= seconds:
                self.awake = False
                self.velocity = Vector2(0.0, 0.0)
                return True
        else:
            self.sleep_timer = 0.0
        return False

    # -- integration -------------------------------------------------------------

    def integrate(self, dt: float, gravity: Vector2 | None = None) -> None:
        """Semi-implicit Euler step applying accumulated forces."""
        if not (self.is_dynamic() and self.awake):
            self.accumulator.reset()
            return
        self.apply_gravity(dt, gravity)
        self.acceleration = self.accumulator.force * self.inverse_mass
        self.velocity = self.velocity + self.acceleration * dt
        damping_factor = math.exp(-self.linear_damping * dt)
        self.velocity = self.velocity * damping_factor + self.accumulator.impulse * self.inverse_mass
        self.position = self.position + self.velocity * dt
        self.angle_degrees = (self.angle_degrees + self.angular_velocity * dt) % 360.0
        self.accumulator.reset()

    def kinetic_energy(self) -> float:
        """Translational kinetic energy in arbitrary engine units."""
        speed_sq = self.velocity.length_squared()
        return 0.5 * self._mass * speed_sq

    def speed(self) -> float:
        """Current scalar speed."""
        return self.velocity.length()


def integrate_all(bodies: List[RigidBody], dt: float, gravity: Vector2 | None = None) -> int:
    """Integrate many bodies; returns how many actually moved."""
    moved = 0
    for body in bodies:
        before = body.position.copy()
        body.integrate(dt, gravity)
        if before != body.position:
            moved += 1
    return moved
