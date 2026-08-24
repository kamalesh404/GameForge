"""Affine transforms for 2D and simplified 3D rendering pipelines."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from src.math.vector import Vector2, Vector3

Mat3 = Tuple[Tuple[float, float, float], ...]


def mat3_identity() -> Mat3:
    """Return the 3x3 identity matrix."""
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def mat3_mul(a: Mat3, b: Mat3) -> Mat3:
    """Multiply two row-major 3x3 matrices."""
    rows: List[Tuple[float, float, float]] = []
    for r in range(3):
        rows.append(tuple(sum(a[r][c] * b[c][k] for c in range(3)) for k in range(3)))
    return tuple(rows)


@dataclass
class Transform2D:
    """Position/rotation/scale decomposition used across ECS and scenes."""

    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    rotation_degrees: float = 0.0
    scale: Vector2 = field(default_factory=lambda: Vector2(1.0, 1.0))

    def matrix(self) -> Mat3:
        """Build the row-major affine matrix for this transform."""
        rad = math.radians(self.rotation_degrees)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        sx, sy = self.scale.x, self.scale.y
        return (
            (cos_a * sx, -sin_a * sy, self.position.x),
            (sin_a * sx, cos_a * sy, self.position.y),
            (0.0, 0.0, 1.0),
        )

    def apply_point(self, point: Vector2) -> Vector2:
        """Transform *point* by this transform's matrix."""
        rotated = point.rotated(self.rotation_degrees)
        return Vector2(rotated.x * self.scale.x + self.position.x,
                       rotated.y * self.scale.y + self.position.y)

    def apply_direction(self, direction: Vector2) -> Vector2:
        """Rotate/scale *direction* ignoring translation."""
        scaled = Vector2(direction.x * self.scale.x, direction.y * self.scale.y)
        return scaled.rotated(self.rotation_degrees)

    def translated(self, offset: Vector2) -> "Transform2D":
        """Return a copy moved by *offset* in local space."""
        return Transform2D(self.position + offset, self.rotation_degrees, self.scale)


def compose_transforms(parent_world: Transform2D, local: Transform2D) -> Transform2D:
    """Compose parent world transform with a child's local transform."""
    world_pos = parent_world.apply_point(local.position)
    return Transform2D(
        position=world_pos,
        rotation_degrees=parent_world.rotation_degrees + local.rotation_degrees,
        scale=Vector2(parent_world.scale.x * local.scale.x, parent_world.scale.y * local.scale.y),
    )


@dataclass
class Transform3D:
    """TRS transform with Euler rotations applied in Z-Y-X order."""

    position: Vector3 = field(default_factory=Vector3)
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    scale: Vector3 = field(default_factory=lambda: Vector3(1.0, 1.0, 1.0))

    def _rotation_matrix(self) -> List[List[float]]:
        rx, ry, rz = (math.radians(a) for a in (self.pitch, self.yaw, self.roll))
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        rot_x = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
        rot_y = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
        rot_z = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

        def mul(p: List[List[float]], q: List[List[float]]) -> List[List[float]]:
            return [[sum(p[i][k] * q[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

        return mul(mul(rot_z, rot_y), rot_x)

    def forward(self) -> Vector3:
        """Unit forward vector (-Z convention) after rotation."""
        r = self._rotation_matrix()
        return Vector3(r[0][2], r[1][2], r[2][2]).normalized() * -1.0

    def apply_point(self, point: Vector3) -> Vector3:
        """Scale, rotate, then translate *point*."""
        r = self._rotation_matrix()
        p = (point.x * self.scale.x, point.y * self.scale.y, point.z * self.scale.z)
        out = [sum(r[i][j] * p[j] for j in range(3)) for i in range(3)]
        return Vector3(out[0] + self.position.x, out[1] + self.position.y, out[2] + self.position.z)


def look_at_basis(eye: Vector3, target: Vector3) -> Tuple[Vector3, Vector3, Vector3]:
    """Return orthonormal (forward, right, up) basis looking at *target*."""
    fwd = (target - eye).normalized()
    world_up = Vector3(0.0, 1.0, 0.0)
    right = fwd.cross(world_up).normalized()
    up = right.cross(fwd).normalized()
    return fwd, right, up


def deg_sequence(values: Sequence[float]) -> List[float]:
    """Wrap a sequence of angles into the ``(-180, 180]`` degree range."""
    return [((v + 180.0) % 360.0) - 180.0 for v in values]
