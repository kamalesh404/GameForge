"""Audio manager: channel mixing, master/bus volume, and spatial panning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.audio.sound import PlaybackState, Sound, SoundLibrary
from src.math.vector import Vector2


@dataclass
class Listener:
    """Reference frame for spatial audio calculations."""

    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    facing_degrees: float = 0.0

    def relative(self, world_position: Vector2) -> Vector2:
        """Offset of *world_position* expressed in listener-local space."""
        return (world_position - self.position).rotated(-self.facing_degrees)


class Channel:
    """A named mixer bus holding sounds plus its own volume/voice budget."""

    def __init__(self, name: str, volume: float = 1.0, max_voices: int = 16) -> None:
        self.name: str = name
        self.volume: float = min(max(volume, 0.0), 1.0)
        self.max_voices: int = max_voices
        self.sounds: List[Sound] = []

    @property
    def effective_gain(self) -> float:
        """Bus-level gain applied to every sound on this channel."""
        return min(max(self.volume, 0.0), 1.0)

    def voice_count(self) -> int:
        """Currently active sounds assigned to this bus."""
        active = {PlaybackState.PLAYING, PlaybackState.PAUSED, PlaybackState.FADING_OUT}
        return sum(1 for s in self.sounds if s.state in active)


class AudioManager:
    """Central playback coordinator with stereo panning for world positions."""

    def __init__(self, master_volume: float = 0.8) -> None:
        self.master_volume: float = min(max(master_volume, 0.0), 1.0)
        self.library: SoundLibrary = SoundLibrary()
        self.channels: Dict[str, Channel] = {
            "sfx": Channel("sfx"),
            "music": Channel("music", max_voices=2),
            "voice": Channel("voice", max_voices=4),
        }
        self.listener: Listener = Listener()
        self.spatial_max_distance: float = 1200.0
        self.muted: bool = False

    def add_channel(self, name: str, volume: float = 1.0, max_voices: int = 16) -> Channel:
        """Create and register a new mixer bus."""
        if name in self.channels:
            raise ValueError(f"channel {name!r} already exists")
        channel = Channel(name, volume=volume, max_voices=max_voices)
        self.channels[name] = channel
        return channel

    def set_channel_volume(self, name: str, volume: float) -> None:
        """Adjust one bus's volume clamped to ``[0, 1]``."""
        if name not in self.channels:
            raise KeyError(f"unknown channel {name!r}")
        self.channels[name].volume = min(max(volume, 0.0), 1.0)

    def pan_for(self, world_position: Vector2) -> float:
        """Stereo pan in ``[-1, 1]`` from listener-relative x offset."""
        rel = self.listener.relative(world_position)
        distance = rel.length()
        if distance < 1e-6 or distance > self.spatial_max_distance:
            return 0.0
        falloff = 1.0 - distance / self.spatial_max_distance
        return min(max(rel.x / distance * falloff, -1.0), 1.0)

    def attenuation_for(self, world_position: Vector2) -> float:
        """Distance-based gain multiplier in ``[0, 1]``."""
        dist = self.listener.position.distance_to(world_position)
        if dist >= self.spatial_max_distance:
            return 0.0
        normalized = 1.0 - dist / self.spatial_max_distance
        return normalized * normalized

    def play(self, sound_name: str, channel_name: str = "sfx",
             world_position: Optional[Vector2] = None,
             loop: Optional[bool] = None) -> Optional[Sound]:
        """Instantiate and start *sound_name*; returns None if voice-starved."""
        channel = self.channels.get(channel_name)
        if channel is None or self.muted or len(channel.sounds) >= channel.max_voices:
            return None
        sound = self.library.instantiate(sound_name)
        sound.loop = sound.loop if loop is None else loop
        gain = channel.effective_gain * self.master_volume
        if world_position is not None:
            gain *= self.attenuation_for(world_position)
        sound.set_volume(sound.base_volume * gain)
        sound.play()
        channel.sounds.append(sound)
        return sound

    def update(self, dt: float) -> int:
        """Tick all channels, pruning finished sounds; returns live voices."""
        live = 0
        for channel in self.channels.values():
            still_playing: List[Sound] = []
            for sound in channel.sounds:
                if sound.advance(dt):
                    still_playing.append(sound)
                    live += 1
            channel.sounds = still_playing
        return live

    def stop_all(self, fade_seconds: float = 0.0) -> int:
        """Stop everything, optionally fading; returns sounds affected."""
        count = 0
        for channel in self.channels.values():
            for sound in channel.sounds:
                if fade_seconds > 0:
                    sound.fade_out(fade_seconds)
                else:
                    sound.stop()
                count += 1
        return count
