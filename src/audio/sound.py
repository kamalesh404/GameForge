"""Sound asset wrapper with playback state, looping, and fades."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class PlaybackState(enum.Enum):
    """Lifecycle of a single sound instance."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    FADING_OUT = "fading_out"
    FINISHED = "finished"


@dataclass
class FadeRequest:
    """Scheduled linear fade applied by the audio mixer."""

    target_volume: float
    duration: float

    def __post_init__(self) -> None:
        self.elapsed: float = 0.0

    @property
    def done(self) -> bool:
        """True when the fade has fully elapsed."""
        return self.elapsed >= self.duration


class Sound:
    """A playable sound instance tracked by the :mod:`src.audio` manager."""

    def __init__(self, name: str, path: str = "", duration: float = 1.0,
                 base_volume: float = 1.0, loop: bool = False) -> None:
        if duration <= 0:
            raise ValueError("duration must be positive")
        self.name: str = name
        self.path: str = path or f"assets/audio/{name}.ogg"
        self.duration: float = duration
        self.base_volume: float = min(max(base_volume, 0.0), 1.0)
        self.loop: bool = loop
        self.pitch: float = 1.0
        self.state: PlaybackState = PlaybackState.STOPPED
        self.volume: float = self.base_volume
        self.position_seconds: float = 0.0
        self.fade: Optional[FadeRequest] = None
        self.metadata: Dict[str, str] = field(default_factory=dict)

    # -- transport -----------------------------------------------------------

    def play(self, restart: bool = True) -> "Sound":
        """Begin (or resume) playback; returns self for chaining."""
        if restart or self.state is not PlaybackState.PAUSED:
            self.position_seconds = 0.0
        self.state = PlaybackState.PLAYING
        return self

    def pause(self) -> None:
        """Halt playback while preserving the playhead."""
        if self.state is PlaybackState.PLAYING or self.state is PlaybackState.FADING_OUT:
            self.state = PlaybackState.PAUSED

    def stop(self) -> None:
        """Return the playhead to zero and mark finished."""
        self.position_seconds = 0.0
        self.state = PlaybackState.FINISHED
        self.fade = None

    def seek(self, seconds: float) -> None:
        """Move the playhead to *seconds*, clamped to duration."""
        self.position_seconds = min(max(seconds, 0.0), self.duration)

    # -- mixing ---------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        """Clamp-set the effective volume in ``[0, 1]``."""
        self.volume = min(max(volume, 0.0), 1.0)

    def fade_in(self, duration: float, target: float | None = None) -> None:
        """Schedule a ramp from silence up to *target* volume."""
        self.set_volume(0.0)
        self.fade = FadeRequest(target_volume=self.base_volume if target is None else target,
                                duration=max(1e-3, duration))
        self.play()

    def fade_out(self, duration: float) -> None:
        """Schedule a ramp down to silence then auto-stop."""
        self.fade = FadeRequest(target_volume=0.0, duration=max(1e-3, duration))
        self.state = PlaybackState.FADING_OUT

    def _apply_fade(self, dt: float) -> None:
        """Advance any scheduled fade; called once per mixer tick."""
        if self.fade is None:
            return
        self.fade.elapsed += dt
        span = max(self.fade.duration, 1e-6)
        t = min(self.fade.elapsed / span, 1.0)
        start_volume = 0.0 if self.fade.target_volume > self.base_volume else self.base_volume
        self.volume = start_volume + (self.fade.target_volume - start_volume) * t
        if self.fade.done:
            if self.fade.target_volume == 0.0:
                self.stop()
            else:
                self.state = PlaybackState.PLAYING
            self.fade = None

    def advance(self, dt: float) -> bool:
        """Tick playback time; returns False when the sound completed."""
        if self.state not in (PlaybackState.PLAYING, PlaybackState.FADING_OUT):
            return not (self.state is PlaybackState.FINISHED and self.loop)
        self._apply_fade(dt)
        self.position_seconds += dt * self.pitch
        if self.position_seconds >= self.duration:
            if self.loop and self.state is PlaybackState.PLAYING:
                self.position_seconds %= self.duration
            else:
                self.stop()
                return False
        return True

    @property
    def remaining(self) -> float:
        """Seconds left before natural completion."""
        return max(0.0, self.duration - self.position_seconds)


class SoundLibrary:
    """Named registry of prototype sounds used to spawn instances."""

    def __init__(self) -> None:
        self._prototypes: Dict[str, Sound] = {}

    def register(self, sound: Sound) -> None:
        """Add or replace a prototype under its name."""
        self._prototypes[sound.name] = sound

    def get(self, name: str) -> Optional[Sound]:
        """Fetch a prototype by name."""
        return self._prototypes.get(name)

    def instantiate(self, name: str) -> Sound:
        """Create an independent playable copy of a registered sound."""
        proto = self._prototypes.get(name)
        if proto is None:
            raise KeyError(f"unknown sound {name!r}")
        clone = Sound(proto.name, proto.path, proto.duration,
                      proto.base_volume, proto.loop)
        clone.metadata = dict(proto.metadata)
        return clone

    def __len__(self) -> int:
        return len(self._prototypes)
