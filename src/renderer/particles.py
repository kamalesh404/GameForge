"""Particle effects: emitters, per-particle forces, lifetimes, and bursts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from src.math.random import SeededRandom
from src.math.vector import Vector2


@dataclass
class Particle:
    """A single simulated particle."""

    position: Vector2
    velocity: Vector2
    max_lifetime: float
    size: float = 4.0
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    drag: float = 0.0

    def __post_init__(self) -> None:
        self.age: float = 0.0

    @property
    def alive(self) -> bool:
        """True until the particle's lifetime elapses."""
        return self.age < self.max_lifetime

    @property
    def life_ratio(self) -> float:
        """Normalized remaining life from 1 (fresh) to 0 (dead)."""
        return max(0.0, 1.0 - self.age / self.max_lifetime)

    def step(self, dt: float) -> None:
        """Advance the particle one tick."""
        if not self.alive:
            return
        damping = math.exp(-self.drag * dt)
        self.velocity = self.velocity * damping
        self.position = self.position + self.velocity * dt
        self.age += dt


ForceField = Callable[["Particle", float], Vector2]


@dataclass
class Emitter:
    """Configuration for a continuous or burst particle source."""

    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    rate_per_second: float = 40.0
    speed_range: Tuple[float, float] = (20.0, 90.0)
    lifetime_range: Tuple[float, float] = (0.4, 1.4)
    size_range: Tuple[float, float] = (2.0, 6.0)
    spread_degrees: float = 360.0
    direction_degrees: float = 90.0
    colors: List[Tuple[int, int, int, int]] = field(
        default_factory=lambda: [(255, 255, 255, 255), (255, 180, 60, 255)]
    )
    initial_velocity: Vector2 | None = None
    gravity: Vector2 = field(default_factory=lambda: Vector2(0.0, -160.0))
    enabled: bool = True

    def spawn_one(self, rng: SeededRandom) -> Particle:
        """Create a randomized particle from this emitter's parameters."""
        angle = rng.uniform(-self.spread_degrees * 0.5, self.spread_degrees * 0.5) + self.direction_degrees
        speed = rng.uniform(*self.speed_range)
        base = Vector2.from_angle(angle, speed)
        if self.initial_velocity is not None:
            base = base + self.initial_velocity
        return Particle(
            position=self.position.copy(),
            velocity=base,
            max_lifetime=rng.uniform(*self.lifetime_range),
            size=rng.uniform(*self.size_range),
            color=rng.choice(self.colors),
            drag=0.6,
        )


class ParticleSystem:
    """Owns live particles and steps them with global force fields."""

    def __init__(self, max_particles: int = 2048, seed: int = 99) -> None:
        self.max_particles: int = max_particles
        self.particles: List[Particle] = []
        self.emitters: List[Emitter] = []
        self.force_fields: List[ForceField] = []
        self.rng: SeededRandom = SeededRandom(seed)
        self._spawn_accumulator: float = 0.0
        self.total_spawned: int = 0

    def add_emitter(self, emitter: Emitter) -> Emitter:
        """Begin emitting from *emitter* every update."""
        self.emitters.append(emitter)
        return emitter

    def add_force_field(self, field_fn: ForceField) -> None:
        """Register a spatial force applied to all live particles."""
        self.force_fields.append(field_fn)

    def burst(self, origin: Vector2, count: int, speed: Tuple[float, float] = (50.0, 220.0)) -> int:
        """Instantly explode *count* particles outward from *origin*."""
        spawned = 0
        temp = Emitter(position=origin, rate_per_second=0.0, speed_range=speed,
                       lifetime_range=(0.25, 0.9))
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break
            particle = temp.spawn_one(self.rng)
            particle.gravity = Vector2(0.0, -320.0)
            self.particles.append(particle)
            spawned += 1
        self.total_spawned += spawned
        return spawned

    def _emit_continuous(self, dt: float) -> None:
        """Accumulate fractional spawns for every active emitter."""
        for emitter in self.emitters:
            if not emitter.enabled:
                continue
            self._spawn_accumulator += emitter.rate_per_second * dt
            while self._spawn_accumulator >= 1.0 and len(self.particles) < self.max_particles:
                self.particles.append(emitter.spawn_one(self.rng))
                self.total_spawned += 1
                self._spawn_accumulator -= 1.0

    def update(self, dt: float) -> None:
        """Emit, integrate forces, and reap expired particles."""
        self._emit_continuous(dt)
        alive: List[Particle] = []
        for particle in self.particles:
            if not particle.alive:
                continue
            for field_fn in self.force_fields:
                pull = field_fn(particle, dt)
                particle.velocity = particle.velocity + pull * dt
            if any(e.gravity.length() > 0 for e in self.emitters):
                pass
            particle.step(dt)
            if particle.alive:
                alive.append(particle)
        self.particles = alive

    def draw_commands(self) -> List[Tuple[Vector2, float, Tuple[int, int, int, int]]]:
        """Renderer-friendly tuples of (position, size, faded color)."""
        commands: List[Tuple[Vector2, float, Tuple[int, int, int, int]]] = []
        for p in self.particles:
            fade = p.life_ratio
            r, g, b, a = p.color
            commands.append((p.position.copy(), p.size * (0.5 + 0.5 * fade),
                             (r, g, b, int(a * fade))))
        return commands

    @property
    def live_count(self) -> int:
        """Number of currently simulated particles."""
        return len(self.particles)

    def clear(self) -> None:
        """Kill every particle immediately."""
        self.particles.clear()

    def attractor_at(self, center: Vector2, strength: float) -> None:
        """Shortcut registering a radial attraction/repulsion field."""
        def field(particle: Particle, _dt: float) -> Vector2:
            offset = center - particle.position
            dist = max(offset.length(), 8.0)
            return offset.normalized() * strength * (100.0 / dist)

        self.add_force_field(field)


def wind_field(direction: Vector2, gustiness: float = 0.3) -> ForceField:
    """Build a gently fluctuating horizontal wind callback."""
    rng = SeededRandom(seed=5)

    def apply(_particle: Particle, _dt: float) -> Vector2:
        jitter = rng.uniform(1.0 - gustiness, 1.0 + gustiness)
        return direction * jitter * 30.0

    return apply


def vortex_field(center: Vector2, spin: float) -> ForceField:
    """Tangential swirl around *center*; positive *spin* rotates CCW."""
    def apply(particle: Particle, _dt: float) -> Vector2:
        rel = particle.position - center
        tangential = Vector2(-rel.y, rel.x).normalized()
        return tangential * spin

    return apply
