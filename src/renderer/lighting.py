"""Light composition: ambient, directional, and point lights with falloff."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.math.vector import Vector2

Color = Tuple[int, int, int]


class Light:
    """Base class carrying colour, intensity, and an enabled flag."""

    def __init__(self, color: Color = (255, 255, 255), intensity: float = 1.0) -> None:
        self.color: Color = color
        self.intensity: float = max(0.0, intensity)
        self.enabled: bool = True
        self.casts_shadows: bool = False

    def contribution_at(self, _point: Vector2) -> float:
        """Illumination multiplier supplied at a world position."""
        return 0.0 if not self.enabled else self.intensity


@dataclass
class AmbientLight(Light):
    """Global minimum illumination applied everywhere uniformly."""

    def __init__(self, color: Color = (70, 70, 90), intensity: float = 0.25) -> None:
        super().__init__(color, intensity)
        self.name: str = "ambient"

    def contribution_at(self, _point: Vector2) -> float:
        """Constant everywhere while enabled."""
        return super().contribution_at(_point)


@dataclass
class DirectionalLight(Light):
    """Sun-like light with parallel rays and optional shadow casting."""

    direction_degrees: float = 45.0
    shadow_length: float = 600.0

    def __post_init__(self) -> None:
        self.casts_shadows: bool = True

    def unit_direction(self) -> Vector2:
        """Normalized ray direction."""
        return Vector2.from_angle(self.direction_degrees)

    def contribution_at(self, point: Vector2) -> float:
        """Directional light is uniform; shadows handled by the system."""
        return super().contribution_at(point)


@dataclass
class PointLight(Light):
    """Radial light source with configurable quadratic falloff radius."""

    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    radius: float = 256.0
    falloff_power: float = 2.0

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("radius must be positive")

    def contribution_at(self, point: Vector2) -> float:
        """Smooth inverse-square style attenuation within *radius*."""
        base = super().contribution_at(point)
        if base == 0.0:
            return 0.0
        dist = point.distance_to(self.position)
        if dist >= self.radius:
            return 0.0
        normalized = 1.0 - (dist / self.radius)
        return base * (normalized ** self.falloff_power)


class ShadowCaster:
    """An occluder segment blocking directional/point light rays."""

    def __init__(self, start: Vector2, end: Vector2, softness: float = 0.5) -> None:
        self.start: Vector2 = start
        self.end: Vector2 = end
        self.softness: float = min(max(softness, 0.0), 1.0)

    def blocks(self, origin: Vector2, target: Vector2) -> bool:
        """Segment-vs-ray intersection test between *origin*/*target*."""
        seg = self.end - self.start
        ray = target - origin
        denom = seg.cross(ray)
        if abs(denom) < 1e-9:
            return False
        t = (origin - self.start).cross(ray) / denom
        u = (origin - self.start).cross(seg) / denom
        return 0.0 <= t <= 1.0 and u >= 0.0


class LightingSystem:
    """Composites all registered lights into per-point illumination."""

    def __init__(self, ambient: Optional[AmbientLight] = None,
                 max_lights: int = 32) -> None:
        self.ambient: AmbientLight = ambient or AmbientLight()
        self.lights: List[Light] = [self.ambient]
        self.shadow_casters: List[ShadowCaster] = []
        self.max_lights: int = max_lights
        self.exposure: float = 1.0

    def add_light(self, light: Light) -> Light:
        """Register a light unless capacity is exhausted."""
        if len(self.lights) >= self.max_lights:
            raise OverflowError(f"light budget of {self.max_lights} exceeded")
        self.lights.append(light)
        return light

    def remove_light(self, light: Light) -> bool:
        """Unregister a light (ambient cannot be removed)."""
        if light is self.ambient:
            return False
        if light in self.lights:
            self.lights.remove(light)
            return True
        return False

    def add_caster(self, caster: ShadowCaster) -> None:
        """Add an occluder participating in shadow tests."""
        self.shadow_casters.append(caster)

    def illuminate(self, point: Vector2) -> Tuple[float, List[Light]]:
        """Total light at *point* plus the lights that contributed."""
        total = 0.0
        contributing: List[Light] = []
        for light in self.lights:
            amount = light.contribution_at(point)
            if amount <= 0.0:
                continue
            if isinstance(light, PointLight) and any(
                c.blocks(light.position, point) for c in self.shadow_casters
            ):
                continue
            if isinstance(light, DirectionalLight):
                blocked = any(c.blocks(point + light.unit_direction() * 8.0, point)
                              for c in self.shadow_casters)
                if blocked:
                    continue
            total += amount
            contributing.append(light)
        return min(total * self.exposure, 4.0), contributing

    def brightness_byte(self, point: Vector2) -> int:
        """Quantized brightness for headless rendering pipelines."""
        level, _ = self.illuminate(point)
        gamma = math.pow(min(level, 1.0), 1.0 / 2.2)
        return int(gamma * 255)
