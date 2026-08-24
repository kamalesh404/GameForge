"""Deterministic randomness, value noise, and interpolation utilities."""

from __future__ import annotations

import math
import random
from typing import Dict, Hashable, Sequence, TypeVar

T = TypeVar("T")


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between *a* and *b* by unclamped factor *t*."""
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    """Hermite smoothing of *t*: 3t^2 - 2t^3, clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def remap(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    """Re-map *value* from one range to another without clamping."""
    if in_max == in_min:
        return out_min
    t = (value - in_min) / (in_max - in_min)
    return out_min + (out_max - out_min) * t


class SeededRandom:
    """Thin wrapper around :class:`random.Random` guaranteeing reproducibility."""

    def __init__(self, seed: int = 1337) -> None:
        self.seed: int = seed
        self._rng = random.Random(seed)

    def reseed(self, seed: int) -> None:
        """Restart the stream from a new *seed*."""
        self.seed = seed
        self._rng = random.Random(seed)

    def uniform(self, low: float, high: float) -> float:
        """Random float in ``[low, high)``."""
        return self._rng.uniform(low, high)

    def int_range(self, low: int, high: int) -> int:
        """Random integer in ``[low, high]`` inclusive."""
        return self._rng.randint(low, high)

    def choice(self, items: Sequence[T]) -> T:
        """Pick one element uniformly from *items*."""
        return self._rng.choice(items)

    def weighted_choice(self, items: Sequence[T], weights: Sequence[float]) -> T:
        """Pick one element according to *weights*."""
        if len(items) != len(weights):
            raise ValueError("items and weights must have equal length")
        return self._rng.choices(list(items), weights=list(weights), k=1)[0]

    def chance(self, probability: float) -> bool:
        """Return True with *probability* in ``[0, 1]``."""
        return self._rng.random() < probability

    def shuffle(self, items: list) -> None:
        """Shuffle *items* in place deterministically."""
        self._rng.shuffle(items)


def _hash_lattice(x: int, y: int, seed: int) -> float:
    """Deterministic hash of a lattice coordinate to ``[0, 1)``."""
    h = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


class ValueNoise:
    """Seamless seeded value noise with fractal brownian motion."""

    def __init__(self, seed: int = 42) -> None:
        self.seed: int = seed

    def noise1d(self, x: float) -> float:
        """Smooth noise along a line, output in ``[0, 1]``."""
        x0, x1 = math.floor(x), math.floor(x) + 1
        t = smoothstep(x - math.floor(x))
        return lerp(_hash_lattice(x0, 0, self.seed), _hash_lattice(x1, 0, self.seed), t)

    def noise2d(self, x: float, y: float) -> float:
        """Bilinearly smoothed noise on a plane, output in ``[0, 1]``."""
        fx, fy = math.floor(x), math.floor(y)
        tx, ty = smoothstep(x - fx), smoothstep(y - fy)
        top = lerp(_hash_lattice(fx, fy, self.seed), _hash_lattice(fx + 1, fy, self.seed), tx)
        bottom = lerp(_hash_lattice(fx, fy + 1, self.seed), _hash_lattice(fx + 1, fy + 1, self.seed), ty)
        return lerp(top, bottom, ty)

    def fbm(self, x: float, y: float = 0.0, octaves: int = 4, persistence: float = 0.5) -> float:
        """Sum *octaves* of noise with halving amplitude, output in ``[0, 1]``."""
        total, amplitude, frequency, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += self.noise2d(x * frequency, y * frequency) * amplitude
            norm += amplitude
            amplitude *= persistence
            frequency *= 2.0
        return total / norm if norm else 0.0


class MemoCache(dict):
    """Dict subclass exposing a bounded ``remember`` helper for hot paths."""

    def __init__(self, capacity: int = 1024) -> None:
        super().__init__()
        self.capacity: int = capacity

    def remember(self, key: Hashable, producer) -> object:
        """Return cached *key*, computing via *producer* on first miss."""
        if key not in self:
            if len(self) >= self.capacity:
                self.pop(next(iter(self)))
            self[key] = producer()
        return self[key]


default_rng = SeededRandom()
noise = ValueNoise()
_cache_registry: Dict[str, MemoCache] = {}
