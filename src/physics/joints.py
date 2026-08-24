"""Constraints linking two bodies: distance, revolute, and prismatic joints."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from src.math.vector import Vector2
from src.physics.rigidbody import RigidBody


class Joint(ABC):
    """Base constraint solved once per physics step."""

    def __init__(self, body_a: RigidBody, body_b: RigidBody) -> None:
        self.body_a: RigidBody = body_a
        self.body_b: RigidBody = body_b
        self.enabled: bool = True
        self.break_force: float | None = None  # joint snaps when exceeded
        self.last_error: float = 0.0

    @abstractmethod
    def solve(self) -> float:
        """Apply corrective impulses; returns residual error magnitude."""

    def should_break(self) -> bool:
        """True when the last solve overstayed the break threshold."""
        return self.break_force is not None and self.last_error > (self.break_force or 0.0)


class DistanceJoint(Joint):
    """Keeps two anchor points a fixed distance apart like a stiff rod."""

    def __init__(self, body_a: RigidBody, body_b: RigidBody, length: float = 100.0,
                 stiffness: float = 0.6, damping: float = 0.1) -> None:
        super().__init__(body_a, body_b)
        self.length: float = length
        self.stiffness: float = stiffness
        self.damping: float = damping

    def current_distance(self) -> float:
        """Live separation between the two body centers."""
        return self.body_a.position.distance_to(self.body_b.position)

    def solve(self) -> float:
        """Pull/push centers toward the rest length."""
        if not self.enabled:
            return 0.0
        delta = self.body_b.position - self.body_a.position
        dist = max(delta.length(), 1e-9)
        direction = delta * (1.0 / dist)
        inv_sum = self.body_a.inverse_mass + self.body_b.inverse_mass
        if inv_sum == 0:
            return 0.0
        error = dist - self.length
        correction = direction * (error * self.stiffness / inv_sum)
        self.body_a.position = self.body_a.position + correction * self.body_a.inverse_mass
        self.body_b.position = self.body_b.position - correction * self.body_b.inverse_mass
        rel_vel = (self.body_b.velocity - self.body_a.velocity).dot(direction)
        jv = -rel_vel * self.damping / inv_sum
        impulse_vec = direction * jv
        self.body_a.velocity = self.body_a.velocity - impulse_vec * self.body_a.inverse_mass
        self.body_b.velocity = self.body_b.velocity + impulse_vec * self.body_b.inverse_mass
        self.last_error = abs(error)
        return self.last_error


class RevoluteJoint(Joint):
    """Pins the two bodies together at a shared world anchor point."""

    def __init__(self, body_a: RigidBody, body_b: RigidBody, anchor: Vector2) -> None:
        super().__init__(body_a, body_b)
        self.anchor: Vector2 = anchor
        self.stiffness: float = 0.8

    def solve(self) -> float:
        """Drag both bodies' positions toward the shared anchor."""
        if not self.enabled:
            return 0.0
        inv_sum = self.body_a.inverse_mass + self.body_b.inverse_mass
        if inv_sum == 0:
            return 0.0
        err_a = self.anchor - self.body_a.position
        err_b = self.anchor - self.body_b.position
        total_err = err_a.length() + err_b.length()
        share = self.stiffness / inv_sum
        move_a = err_a * (share * self.body_a.inverse_mass)
        move_b = err_b * (share * self.body_b.inverse_mass)
        self.body_a.position = self.body_a.position + move_a
        self.body_b.position = self.body_b.position + move_b
        mid_vel = (self.body_a.velocity + self.body_b.velocity) * 0.5
        self.body_a.velocity = mid_vel
        self.body_b.velocity = mid_vel
        self.last_error = total_err
        return total_err


class PrismaticJoint(Joint):
    """Slider allowing motion only along one axis between limits."""

    def __init__(self, body_a: RigidBody, body_b: RigidBody, axis_degrees: float = 0.0,
                 min_limit: float = -math.inf, max_limit: float = math.inf,
                 stiffness: float = 0.7) -> None:
        super().__init__(body_a, body_b)
        self.axis_degrees: float = axis_degrees
        self.min_limit: float = min_limit
        self.max_limit: float = max_limit
        self.stiffness: float = stiffness

    def axis(self) -> Vector2:
        """Unit vector of permitted sliding."""
        return Vector2.from_angle(self.axis_degrees)

    def projection(self) -> float:
        """Signed offset of B relative to A along the axis."""
        rel = self.body_b.position - self.body_a.position
        return rel.dot(self.axis())

    def solve(self) -> float:
        """Zero perpendicular velocity and clamp axial travel to limits."""
        if not self.enabled:
            return 0.0
        axis = self.axis()
        perp = Vector2(-axis.y, axis.x)
        inv_sum = self.body_a.inverse_mass + self.body_b.inverse_mass
        if inv_sum == 0:
            return 0.0
        rel_vel_perp = (self.body_b.velocity - self.body_a.velocity).dot(perp)
        fix = perp * (-rel_vel_perp * self.stiffness / inv_sum)
        self.body_b.velocity = self.body_b.velocity + fix * self.body_b.inverse_mass
        self.body_a.velocity = self.body_a.velocity - fix * self.body_a.inverse_mass
        proj = self.projection()
        error = 0.0
        if proj < self.min_limit:
            error = self.min_limit - proj
        elif proj > self.max_limit:
            error = -(proj - self.max_limit)
        push = axis * (error * self.stiffness / inv_sum)
        self.body_b.position = self.body_b.position + push * self.body_b.inverse_mass
        self.body_a.position = self.body_a.position - push * self.body_a.inverse_mass
        self.last_error = abs(error)
        return self.last_error


def solve_joints(joints: list[Joint], iterations: int = 3) -> float:
    """Iteratively relax every enabled joint; returns worst residual."""
    worst = 0.0
    for _ in range(max(1, iterations)):
        for joint in joints:
            worst = max(worst, joint.solve())
    return worst
