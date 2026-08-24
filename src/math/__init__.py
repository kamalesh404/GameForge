"""Math package: vectors, affine transforms, and procedural randomness."""

from src.math.random import SeededRandom, ValueNoise, lerp, remap, smoothstep
from src.math.transform import Transform2D, Transform3D, compose_transforms
from src.math.vector import Vector2, Vector3, Vector4

__all__ = [
    "SeededRandom",
    "ValueNoise",
    "lerp",
    "remap",
    "smoothstep",
    "Transform2D",
    "Transform3D",
    "compose_transforms",
    "Vector2",
    "Vector3",
    "Vector4",
]
