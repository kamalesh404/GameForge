"""Physics world: broadphase quadtree, narrowphase dispatch, and solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Set, Tuple

from src.math.vector import Vector2
from src.physics.collider import (
    AABB,
    BaseCollider,
    CircleCollider,
    detect,
)
from src.physics.collider import AABBCollider  # noqa: F401 - re-exported convenience
from src.physics.rigidbody import RigidBody


class Quadtree:
    """Spatial partition accelerating pair generation for many colliders."""

    MAX_OBJECTS: int = 6
    MAX_DEPTH: int = 8

    def __init__(self, bounds: AABB, depth: int = 0) -> None:
        self.bounds: AABB = bounds
        self.depth: int = depth
        self.items: List[Tuple[object, AABB]] = []
        self.nodes: List["Quadtree"] = []

    def clear(self) -> None:
        """Reset the tree for the next frame."""
        self.items.clear()
        self.nodes.clear()

    def _split(self) -> None:
        """Create four quadrant children."""
        c = self.bounds.center
        half = self.bounds.size * 0.5
        offsets = ((-half.x, 0), (0, -half.y), (-half.x, -half.y), (0, 0))
        self.nodes = [
            Quadtree(
                AABB(
                    Vector2(c.x + ox, c.y + oy),
                    Vector2(c.x + ox + half.x, c.y + oy + half.y),
                ),
                self.depth + 1,
            )
            for ox, oy in offsets
        ]

    def insert(self, item: object, box: AABB) -> None:
        """Insert *item* occupying *box*, subdividing when saturated."""
        if self.nodes:
            for node in self._quadrants_for(box):
                node.insert(item, box)
                return
            self.items.append((item, box))
            return
        self.items.append((item, box))
        if len(self.items) > Quadtree.MAX_OBJECTS and self.depth < Quadtree.MAX_DEPTH:
            self._split()
            spilled = [entry for entry in self.items if not self._redistribute(entry)]
            self.items = spilled

    def _redistribute(self, entry: Tuple[object, AABB]) -> bool:
        """Try pushing an existing item into children after a split."""
        item, box = entry
        for node in self._quadrants_for(box):
            node.insert(item, box)
            return True
        return False

    def _quadrants_for(self, box: AABB) -> List["Quadtree"]:
        """Children fully containing *box* (at most one fits exactly)."""
        return [n for n in self.nodes if n.bounds.min_corner.x <= box.min_corner.x
                and n.bounds.min_corner.y <= box.min_corner.y
                and n.bounds.max_corner.x >= box.max_corner.x
                and n.bounds.max_corner.y >= box.max_corner.y]

    def query(self, area: AABB) -> Set[object]:
        """Collect candidate items intersecting *area*."""
        found: Set[object] = set()
        if not self.bounds.overlaps(area):
            return found
        for item, box in self.items:
            if box.overlaps(area):
                found.add(item)
        for node in self.nodes:
            found |= node.query(area)
        return found


@dataclass(eq=False)
class BodyBinding:
    """Couples a rigid body to its collision shape (identity-hashed)."""

    body: RigidBody
    shape: BaseCollider
    sensor_only: bool = False


@dataclass(eq=False)
class CollisionPair:
    """A candidate or confirmed pair produced by the solver pipeline."""

    first: BodyBinding
    second: BodyBinding


class PhysicsWorld:
    """Steps rigid-body simulation: integrate, collide, and resolve."""

    def __init__(self, gravity: Vector2 | None = None, world_bounds: AABB | None = None) -> None:
        self.gravity: Vector2 = gravity or Vector2(0.0, -980.0)
        self.world_bounds: AABB = world_bounds or AABB(Vector2(-5000, -5000), Vector2(5000, 5000))
        self.bindings: List[BodyBinding] = []
        self.quadtree: Quadtree = Quadtree(self.world_bounds)
        self.contact_listeners: List[object] = []
        self.position_correction: float = 0.8
        self.slop: float = 0.05
        self.step_count: int = 0

    def add_body(self, body: RigidBody, shape: BaseCollider, sensor_only: bool = False) -> BodyBinding:
        """Register *body*/\u200b*shape* couple and return its binding."""
        binding = BodyBinding(body=body, shape=shape, sensor_only=sensor_only)
        self.bindings.append(binding)
        return binding

    def remove_body(self, binding: BodyBinding) -> bool:
        """Unregister a previously added binding."""
        if binding in self.bindings:
            self.bindings.remove(binding)
            return True
        return False

    def _rebuild_broadphase(self) -> None:
        """Refresh the quadtree from current collider bounds."""
        self.quadtree.clear()
        for binding in self.bindings:
            self.quadtree.insert(binding, binding.shape.bounds())

    def _candidate_pairs(self) -> Iterator[CollisionPair]:
        """Yield unique overlapping-bounds pairs from the broadphase."""
        seen: Set[Tuple[int, int]] = set()
        for binding in self.bindings:
            area = binding.shape.bounds().expand(4.0)
            for other in self.quadtree.query(area):
                if other is binding:
                    continue
                key = (id(min(binding, other, key=id)), id(max(binding, other, key=id)))
                if key not in seen:
                    seen.add(key)
                    yield CollisionPair(first=binding, second=other)

    def _resolve_pair(self, contact_normal: Vector2, depth: float,
                      a: BodyBinding, b: BodyBinding) -> bool:
        """Impulse response plus positional correction for one contact."""
        ba, bb = a.body, b.body
        if not (ba.is_dynamic() or bb.is_dynamic()):
            return False
        inv_a, inv_b = ba.inverse_mass, bb.inverse_mass
        total_inv = inv_a + inv_b
        if total_inv == 0:
            return False
        relative = bb.velocity - ba.velocity
        along_normal = relative.dot(contact_normal)
        restitution = min(ba.restitution, bb.restitution)
        if along_normal > 0:
            j_impulse = -(1.0 + restitution) * along_normal / total_inv
            impulse_vec = contact_normal * j_impulse
            ba.velocity = ba.velocity - impulse_vec * inv_a
            bb.velocity = bb.velocity + impulse_vec * inv_b
        correction = max(depth - self.slop, 0.0) / total_inv * self.position_correction
        push = contact_normal * correction
        ba.position = ba.position - push * inv_a
        bb.position = bb.position + push * inv_b
        a.shape.center = ba.position.copy()
        b.shape.center = bb.position.copy()
        return True

    def step(self, dt: float) -> int:
        """Advance the simulation one tick; returns contacts resolved."""
        from src.physics.collider import PolygonCollider  # local import avoids cycle cost

        for binding in self.bindings:
            binding.shape.center = binding.body.position
        for binding in self.bindings:
            binding.body.integrate(dt, self.gravity)

        self._rebuild_broadphase()
        resolved = 0
        for pair in self._candidate_pairs():
            sa, sb = pair.first.shape, pair.second.shape
            if isinstance(sa, CircleCollider) or isinstance(sb, CircleCollider):
                pass
            contact = detect(sa, sb)
            if contact is None:
                continue
            normal, depth = contact
            if pair.first.sensor_only or pair.second.sensor_only:
                continue
            if isinstance(sa, PolygonCollider) or isinstance(sb, PolygonCollider):
                normal = normal.normalized() if normal.length() > 0 else normal
            if self._resolve_pair(normal, depth, pair.first, pair.second):
                resolved += 1
                for listener in self.contact_listeners:
                    handler = getattr(listener, "on_contact", None)
                    if callable(handler):
                        handler(pair.first, pair.second, normal, depth)
        self.step_count += 1
        return resolved

    def raycast_ground(self, point: Vector2) -> Optional[BaseCollider]:
        """Return the topmost collider containing *point*, if any."""
        hits = [b for b in self.bindings if not b.sensor_only and b.shape.contains_point(point)]
        return hits[-1].shape if hits else None

    @property
    def body_count(self) -> int:
        """Number of registered bindings."""
        return len(self.bindings)
