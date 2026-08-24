"""Keyframe animation clips with easing and a hierarchical state machine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

EasingFn = Callable[[float], float]


def linear(t: float) -> float:
    """Constant-speed easing."""
    return t


def ease_in_quad(t: float) -> float:
    """Accelerating quadratic ease."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Decelerating quadratic ease."""
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out_sine(t: float) -> float:
    """Symmetric sinusoidal ease."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def bounce_out(t: float) -> float:
    """Exponentially decaying bounce used for landing impacts."""
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


EASINGS: Dict[str, EasingFn] = {
    "linear": linear,
    "in_quad": ease_in_quad,
    "out_quad": ease_out_quad,
    "in_out_sine": ease_in_out_sine,
    "bounce_out": bounce_out,
}


@dataclass
class Keyframe:
    """A value sample at a normalized time inside a clip."""

    time: float
    value: float
    easing: str = "linear"

    def eased_t(self, raw_t: float) -> float:
        """Apply this key's easing to progress since the previous key."""
        return EASINGS.get(self.easing, linear)(max(0.0, min(1.0, raw_t)))


class AnimationClip:
    """A timeline of keyframes that samples to a scalar property value."""

    def __init__(self, name: str, duration: float = 1.0, loop: bool = True) -> None:
        self.name: str = name
        self.duration: float = max(1e-6, duration)
        self.loop: bool = loop
        self.keyframes: List[Keyframe] = []

    def add_key(self, time: float, value: float, easing: str = "linear") -> "AnimationClip":
        """Append (sorted later) a keyframe; returns self for chaining."""
        self.keyframes.append(Keyframe(time=time, value=value, easing=easing))
        self.keyframes.sort(key=lambda k: k.time)
        return self

    def sample(self, elapsed: float) -> float:
        """Interpolated value at *elapsed* seconds into the clip."""
        keys = self.keyframes
        if not keys:
            return 0.0
        t = elapsed % self.duration if self.loop else min(elapsed, self.duration)
        if t <= keys[0].time:
            return keys[0].value
        if t >= keys[-1].time:
            return keys[-1].value
        for i in range(len(keys) - 1):
            lo, hi = keys[i], keys[i + 1]
            if lo.time <= t <= hi.time:
                span = max(hi.time - lo.time, 1e-9)
                local = hi.eased_t((t - lo.time) / span)  # easing of the arriving key
                return lo.value + (hi.value - lo.value) * local
        return keys[-1].value


@dataclass
class AnimationState:
    """One node in the animation state machine."""

    clip: AnimationClip
    on_complete: Optional[str] = None
    speed: float = 1.0
    transitions: List[Tuple[str, Callable[[], bool]]] = field(default_factory=list)


class AnimationStateMachine:
    """Drives the active clip and evaluates transition predicates."""

    def __init__(self) -> None:
        self.states: Dict[str, AnimationState] = {}
        self.current: Optional[AnimationState] = None
        self.current_name: str = ""
        self._elapsed: float = 0.0
        self.transitions_fired: int = 0

    def add_state(self, name: str, state: AnimationState) -> None:
        """Register *state* under *name*."""
        self.states[name] = state

    def play(self, name: str, restart: bool = False) -> None:
        """Switch to *name*, optionally restarting its clock."""
        state = self.states.get(name)
        if state is None:
            raise KeyError(f"unknown animation state {name!r}")
        if self.current_name == name and not restart:
            return
        self.current_name = name
        self.current = state
        self._elapsed = 0.0

    def update(self, dt: float) -> float:
        """Advance time, evaluate transitions; returns sampled value."""
        if self.current is None:
            return 0.0
        self._elapsed += dt * self.current.speed
        clip = self.current.clip
        finished = not clip.loop and self._elapsed >= clip.duration
        for target_name, predicate in self.current.transitions:
            if predicate():
                self.play(target_name)
                self.transitions_fired += 1
                break
        else:
            if finished and self.current.on_complete:
                self.play(self.current.on_complete)
                self.transitions_fired += 1
        return clip.sample(self._elapsed)

    @property
    def elapsed(self) -> float:
        """Seconds accumulated in the current state."""
        return self._elapsed
