"""Vector math primitives shared by every GameForge subsystem."""

from __future__ import annotations

import math
from typing import Iterator, List, Tuple


def _approx(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) <= eps


class Vector2:
    """A 2-component float vector supporting rich operator arithmetic."""

    __slots__ = ("x", "y")

    ZERO = None  # replaced below; keeps type checkers aware of constants
    ONE = None
    UNIT_X = None
    UNIT_Y = None

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x: float = float(x)
        self.y: float = float(y)

    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vector2":
        if scalar == 0:
            raise ZeroDivisionError("cannot divide vector by zero")
        return Vector2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "Vector2":
        return Vector2(-self.x, -self.y)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector2):
            return NotImplemented
        return _approx(self.x, other.x) and _approx(self.y, other.y)

    def __repr__(self) -> str:
        return f"Vector2({self.x:.3f}, {self.y:.3f})"

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y)[index]

    # -- vector algebra ------------------------------------------------------

    def dot(self, other: "Vector2") -> float:
        """Return the dot product with *other*."""
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vector2") -> float:
        """Return the scalar z-component of the 2D cross product."""
        return self.x * other.y - self.y * other.x

    def length_squared(self) -> float:
        """Squared magnitude, cheaper than :meth:`length`."""
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        """Euclidean magnitude of the vector."""
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vector2":
        """Return a unit-length copy, or zero vector if degenerate."""
        mag = self.length()
        return Vector2(0.0, 0.0) if mag == 0 else Vector2(self.x / mag, self.y / mag)

    def rotated(self, degrees: float) -> "Vector2":
        """Rotate counter-clockwise by *degrees* around the origin."""
        rad = math.radians(degrees)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        return Vector2(self.x * cos_a - self.y * sin_a, self.x * sin_a + self.y * cos_a)

    def angle_degrees(self) -> float:
        """Direction angle in degrees within ``(-180, 180]``."""
        return math.degrees(math.atan2(self.y, self.x))

    def distance_to(self, other: "Vector2") -> float:
        """Euclidean distance between two points."""
        return (other - self).length()

    def lerp(self, other: "Vector2", t: float) -> "Vector2":
        """Interpolate toward *other* by factor *t*."""
        return Vector2(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)

    def reflect(self, normal: "Vector2") -> "Vector2":
        """Mirror this vector about *normal*."""
        n = normal.normalized()
        return self - n * (2.0 * self.dot(n))

    def copy(self) -> "Vector2":
        """Return an independent duplicate."""
        return Vector2(self.x, self.y)

    def as_tuple(self) -> Tuple[float, float]:
        """Convert to a plain ``(x, y)`` tuple."""
        return (self.x, self.y)

    @staticmethod
    def from_angle(degrees: float, length: float = 1.0) -> "Vector2":
        """Construct a unit direction pointing at *degrees*."""
        rad = math.radians(degrees)
        return Vector2(math.cos(rad) * length, math.sin(rad) * length)


Vector2.ZERO = Vector2(0.0, 0.0)
Vector2.ONE = Vector2(1.0, 1.0)
Vector2.UNIT_X = Vector2(1.0, 0.0)
Vector2.UNIT_Y = Vector2(0.0, 1.0)


class Vector3:
    """A 3-component vector used by lighting, audio, and 3D transforms."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __add__(self, o: "Vector3") -> "Vector3":
        return Vector3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vector3") -> "Vector3":
        return Vector3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> "Vector3":
        return Vector3(self.x * s, self.y * s, self.z * s)

    __rmul__ = __mul__

    def __repr__(self) -> str:
        return f"Vector3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

    def dot(self, o: "Vector3") -> float:
        """Dot product with *o*."""
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vector3") -> "Vector3":
        """Right-handed cross product with *o*."""
        return Vector3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def length(self) -> float:
        """Magnitude of the vector."""
        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vector3":
        """Unit copy, or zero vector when degenerate."""
        m = self.length()
        return Vector3(0.0, 0.0, 0.0) if m == 0 else self / m

    def __truediv__(self, s: float) -> "Vector3":
        if s == 0:
            raise ZeroDivisionError("cannot divide vector by zero")
        return Vector3(self.x / s, self.y / s, self.z / s)


class Vector4:
    """Homogeneous RGBA/color or clip-space vector."""

    __slots__ = ("x", "y", "z", "w")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0) -> None:
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)

    @classmethod
    def from_rgba(cls, rgba: Tuple[int, int, int, int]) -> "Vector4":
        """Build a 0..1 vector from 8-bit RGBA components."""
        r, g, b, a = rgba
        return cls(r / 255.0, g / 255.0, b / 255.0, a / 255.0)

    def to_rgba(self) -> Tuple[int, int, int, int]:
        """Quantize back to 8-bit RGBA channels."""
        channels: List[int] = [max(0, min(255, round(c * 255))) for c in (self.x, self.y, self.z, self.w)]
        return (channels[0], channels[1], channels[2], channels[3])

    def __repr__(self) -> str:
        return f"Vector4({self.x:.3f}, {self.y:.3f}, {self.z:.3f}, {self.w:.3f})"
