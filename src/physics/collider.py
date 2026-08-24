"""Collision shapes and detection routines: AABB, circle, polygon (SAT)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from src.math.vector import Vector2


@dataclass
class AABB:
    """Axis-aligned bounding box expressed by opposite corners."""

    min_corner: Vector2
    max_corner: Vector2

    def overlaps(self, other: "AABB") -> bool:
        """True when the two boxes intersect."""
        return (self.min_corner.x <= other.max_corner.x and self.max_corner.x >= other.min_corner.x
                and self.min_corner.y <= other.max_corner.y and self.max_corner.y >= other.min_corner.y)

    def contains_point(self, point: Vector2) -> bool:
        """True when *point* lies inside inclusive bounds."""
        return (self.min_corner.x <= point.x <= self.max_corner.x
                and self.min_corner.y <= point.y <= self.max_corner.y)

    def expand(self, margin: float) -> "AABB":
        """Return a copy grown by *margin* on every side."""
        m = Vector2(margin, margin)
        return AABB(self.min_corner - m, self.max_corner + m)

    @property
    def size(self) -> Vector2:
        """Extent of the box."""
        return self.max_corner - self.min_corner

    @property
    def center(self) -> Vector2:
        """Midpoint of the box."""
        return (self.min_corner + self.max_corner) * 0.5


class BaseCollider:
    """Abstract shape centred at a movable position."""

    def __init__(self, center: Vector2) -> None:
        self.center: Vector2 = center

    def bounds(self) -> AABB:
        """World-space bounding box used by broadphase."""
        raise NotImplementedError

    def contains_point(self, point: Vector2) -> bool:
        """Point-in-shape test."""
        return self.bounds().contains_point(point)


class AABBCollider(BaseCollider):
    """Box collider defined by half-extents."""

    def __init__(self, center: Vector2, half_extents: Vector2) -> None:
        super().__init__(center)
        self.half_extents: Vector2 = half_extents

    def bounds(self) -> AABB:
        return AABB(self.center - self.half_extents, self.center + self.half_extents)


class CircleCollider(BaseCollider):
    """Round collider defined by radius."""

    def __init__(self, center: Vector2, radius: float) -> None:
        super().__init__(center)
        self.radius: float = max(1e-6, radius)

    def bounds(self) -> AABB:
        r = Vector2(self.radius, self.radius)
        return AABB(self.center - r, self.center + r)


class PolygonCollider(BaseCollider):
    """Convex polygon whose vertices are offsets from the center."""

    def __init__(self, center: Vector2, vertices: Sequence[Vector2]) -> None:
        super().__init__(center)
        if len(vertices) < 3:
            raise ValueError("polygon needs at least three vertices")
        self.vertices: List[Vector2] = list(vertices)

    def world_vertices(self) -> List[Vector2]:
        """Vertices translated into world space."""
        return [self.center + v for v in self.vertices]

    def bounds(self) -> AABB:
        pts = self.world_vertices()
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        return AABB(Vector2(min(xs), min(ys)), Vector2(max(xs), max(ys)))


def aabb_vs_aabb(a: AABBCollider, b: AABBCollider) -> Optional[Tuple[Vector2, float]]:
    """Return (normal from a to b, penetration) or None when disjoint."""
    dx = b.center.x - a.center.x
    px = a.half_extents.x + b.half_extents.x - abs(dx)
    dy = b.center.y - a.center.y
    py = a.half_extents.y + b.half_extents.y - abs(dy)
    if px <= 0 or py <= 0:
        return None
    if px < py:
        return Vector2(1.0 if dx >= 0 else -1.0, 0.0), px
    return Vector2(0.0, 1.0 if dy >= 0 else -1.0), py


def circle_vs_circle(a: CircleCollider, b: CircleCollider) -> Optional[Tuple[Vector2, float]]:
    """Return (normal a->b, penetration) or None when separated."""
    delta = b.center - a.center
    dist = delta.length()
    radii = a.radius + b.radius
    if dist >= radii:
        return None
    normal = delta.normalized() if dist > 1e-9 else Vector2(1.0, 0.0)
    return normal, radii - dist


def aabb_vs_circle(box: AABBCollider, ball: CircleCollider) -> Optional[Tuple[Vector2, float]]:
    """Circle against box using closest-point sampling."""
    closest = Vector2(
        max(box.center.x - box.half_extents.x, min(ball.center.x, box.center.x + box.half_extents.x)),
        max(box.center.y - box.half_extents.y, min(ball.center.y, box.center.y + box.half_extents.y)),
    )
    delta = ball.center - closest
    dist = delta.length()
    if dist >= ball.radius:
        return None
    if dist < 1e-9:
        return Vector2(0.0, 1.0), ball.radius
    return delta.normalized(), ball.radius - dist


def _project_axis(vertices: Sequence[Vector2], axis: Vector2) -> Tuple[float, float]:
    values = [v.dot(axis) for v in vertices]
    return min(values), max(values)


def sat_polygon(a: PolygonCollider, b: PolygonCollider) -> Optional[Tuple[Vector2, float]]:
    """Separating-axis test for convex polygons."""
    best_depth, best_normal = math.inf, Vector2(0.0, 1.0)
    for source, target in ((a, b), (b, a)):
        verts = source.world_vertices()
        for i in range(len(verts)):
            edge = verts[(i + 1) % len(verts)] - verts[i]
            axis = Vector2(-edge.y, edge.x).normalized()
            lo_a, hi_a = _project_axis(a.world_vertices(), axis)
            lo_b, hi_b = _project_axis(b.world_vertices(), axis)
            overlap = min(hi_a, hi_b) - max(lo_a, lo_b)
            if overlap <= 0:
                return None
            if overlap < best_depth:
                best_depth, best_normal = overlap, axis
                if lo_a > lo_b:
                    best_normal = best_normal * -1.0
    return best_normal, best_depth


Contact = Tuple[Vector2, float]


def detect(shape_a: BaseCollider, shape_b: BaseCollider) -> Optional[Contact]:
    """Dispatch any supported shape pair to its narrowphase routine."""
    pair = (type(shape_a), type(shape_b))
    if pair == (AABBCollider, AABBCollider):
        return aabb_vs_aabb(shape_a, shape_b)  # type: ignore[arg-type]
    if pair == (CircleCollider, CircleCollider):
        return circle_vs_circle(shape_a, shape_b)  # type: ignore[arg-type]
    if pair == (AABBCollider, CircleCollider):
        return aabb_vs_circle(shape_a, shape_b)  # type: ignore[arg-type]
    if pair == (PolygonCollider, PolygonCollider):
        return sat_polygon(shape_a, shape_b)  # type: ignore[arg-type]
    return None
