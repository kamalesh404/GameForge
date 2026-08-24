"""2D camera with follow smoothing, zoom, and trauma-based screen shake."""

from __future__ import annotations

import math
from typing import Optional

from src.math.random import SeededRandom
from src.math.vector import Vector2


class Camera:
    """Transforms world coordinates into a viewport's pixel space."""

    MAX_TRAUMA: float = 1.0

    def __init__(self, viewport_width: int = 1280, viewport_height: int = 720) -> None:
        self.position: Vector2 = Vector2(0.0, 0.0)
        self.zoom: float = 1.0
        self.rotation_degrees: float = 0.0
        self.viewport_size: tuple[int, int] = (viewport_width, viewport_height)
        self.trauma: float = 0.0
        self.max_shake_offset: float = 24.0
        self.max_shake_rotation: float = 3.5
        self.decay_per_second: float = 1.4
        self.bounds: Optional[tuple[Vector2, Vector2]] = None
        self.shake_offset: Vector2 = Vector2(0.0, 0.0)
        self._rng: SeededRandom = SeededRandom(seed=7)

    # -- framing ---------------------------------------------------------------

    def set_viewport(self, width: int, height: int) -> None:
        """Resize the render target this camera maps onto."""
        if width <= 0 or height <= 0:
            raise ValueError("viewport must be positive")
        self.viewport_size = (width, height)

    def set_bounds(self, min_corner: Vector2, max_corner: Vector2) -> None:
        """Constrain the camera center inside the given rectangle."""
        self.bounds = (min_corner, max_corner)

    def clamp_position(self) -> None:
        """Keep the camera inside configured bounds when present."""
        if not self.bounds:
            return
        lo, hi = self.bounds
        self.position = Vector2(max(lo.x, min(hi.x, self.position.x)),
                                max(lo.y, min(hi.y, self.position.y)))

    def follow(self, target: Vector2, dt: float, lerp_factor: float = 6.0) -> None:
        """Smoothly chase *target* using exponential damping."""
        t = 1.0 - math.exp(-lerp_factor * dt)
        self.position = self.position.lerp(target, t)
        self.clamp_position()

    def snap_to(self, target: Vector2) -> None:
        """Teleport the camera to *target* without smoothing."""
        self.position = target.copy()
        self.clamp_position()

    # -- shake -------------------------------------------------------------------

    def add_trauma(self, amount: float) -> None:
        """Inject shake energy, clamped to ``MAX_TRAUMA``."""
        self.trauma = min(Camera.MAX_TRAUMA, self.trauma + amount)

    def update(self, dt: float) -> tuple[Vector2, float]:
        """Decay trauma and cache the frame's shake offset/rotation."""
        self.trauma = max(0.0, self.trauma - self.decay_per_second * dt)
        stress = self.trauma * self.trauma
        angle = self._rng.uniform(0.0, math.tau)
        self.shake_offset = Vector2(math.cos(angle), math.sin(angle)) * (stress * self.max_shake_offset)
        rotation = self._rng.uniform(-1.0, 1.0) * stress * self.max_shake_rotation
        return self.shake_offset.copy(), rotation

    # -- coordinate mapping ---------------------------------------------------------

    def world_to_screen(self, world_point: Vector2) -> Vector2:
        """Project *world_point* into viewport pixel coordinates."""
        relative = (world_point - self.position) * self.zoom
        w, h = self.viewport_size
        return Vector2(w * 0.5 + relative.x + self.shake_offset.x,
                       h * 0.5 - relative.y + self.shake_offset.y)

    def screen_to_world(self, screen_point: Vector2) -> Vector2:
        """Unproject viewport pixels back into world space."""
        w, h = self.viewport_size
        centered = Vector2(screen_point.x - w * 0.5, h * 0.5 - screen_point.y)
        return centered * (1.0 / self.zoom) + self.position

    @property
    def visible_world_rect(self) -> tuple[Vector2, Vector2]:
        """World-space corners of everything currently on screen."""
        half_w = self.viewport_size[0] / (2.0 * self.zoom)
        half_h = self.viewport_size[1] / (2.0 * self.zoom)
        return self.position - Vector2(half_w, half_h), self.position + Vector2(half_w, half_h)

    def is_visible(self, point: Vector2, margin: float = 32.0) -> bool:
        """Culling helper: is *point* within the visible rect plus margin?"""
        lo, hi = self.visible_world_rect
        return (lo.x - margin <= point.x <= hi.x + margin
                and lo.y - margin <= point.y <= hi.y + margin)
