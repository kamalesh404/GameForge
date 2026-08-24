"""Sprite rendering: atlas frames, instances, and ordered batching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.math.vector import Vector2


@dataclass
class SpriteFrame:
    """A rectangular region inside a texture/atlas page."""

    texture_id: str
    x: int = 0
    y: int = 0
    width: int = 32
    height: int = 32

    @property
    def uv_min(self) -> Tuple[float, float]:
        """Normalized top-left UV coordinates."""
        return (self.x / max(1, self.width), self.y / max(1, self.height))

    def contains(self, px: int, py: int) -> bool:
        """True when pixel coordinates fall inside the frame."""
        return (self.x <= px < self.x + self.width) and (self.y <= py < self.y + self.height)


class SpriteAtlas:
    """Maps symbolic names to :class:`SpriteFrame` regions on one page."""

    def __init__(self, name: str, page_size: Tuple[int, int] = (512, 512)) -> None:
        self.name: str = name
        self.page_size: Tuple[int, int] = page_size
        self.frames: Dict[str, SpriteFrame] = {}

    def define(self, key: str, x: int, y: int, width: int, height: int,
               texture_id: str | None = None) -> SpriteFrame:
        """Register a named frame region and return it."""
        frame = SpriteFrame(texture_id or self.name, x=x, y=y, width=width, height=height)
        self.frames[key] = frame
        return frame

    def get(self, key: str) -> Optional[SpriteFrame]:
        """Fetch a frame by key, or None when undefined."""
        return self.frames.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.frames


@dataclass
class SpriteInstance:
    """One drawable sprite submitted to the batch each frame."""

    position: Vector2
    frame_key: str
    layer: int = 0
    z_order: float = 0.0
    scale: float = 1.0
    rotation_degrees: float = 0.0
    tint: Tuple[int, int, int, int] = (255, 255, 255, 255)
    flip_x: bool = False
    flip_y: bool = False

    @property
    def sort_key(self) -> Tuple[int, float]:
        """Deterministic draw ordering key."""
        return (self.layer, self.z_order)


@dataclass
class DrawStats:
    """Counters describing the last completed batch."""

    submitted: int = 0
    drawn: int = 0
    culled: int = 0


class SpriteBatch:
    """Accumulates instances per frame, sorts them, and reports statistics."""

    def __init__(self) -> None:
        self.atlases: Dict[str, SpriteAtlas] = {}
        self._queue: List[SpriteInstance] = []
        self.stats: DrawStats = DrawStats()
        self.sort_enabled: bool = True

    def register_atlas(self, atlas: SpriteAtlas) -> None:
        """Make an atlas available for frame lookups."""
        self.atlases[atlas.name] = atlas

    def resolve_frame(self, frame_key: str) -> Optional[SpriteFrame]:
        """Look up ``atlas:key`` or bare ``key`` across all atlases."""
        if ":" in frame_key:
            atlas_name, key = frame_key.split(":", 1)
            atlas = self.atlases.get(atlas_name)
            return atlas.get(key) if atlas else None
        for atlas in self.atlases.values():
            frame = atlas.get(key=frame_key)
            if frame is not None:
                return frame
        return None

    # -- frame lifecycle ----------------------------------------------------------

    def begin(self) -> None:
        """Clear the submission queue for a new frame."""
        self._queue.clear()
        self.stats = DrawStats()

    def draw(self, instance: SpriteInstance) -> None:
        """Queue *instance*; culling happens at flush time."""
        self._queue.append(instance)

    def flush(self, visible_check=None) -> List[SpriteInstance]:
        """Sort queued sprites and return the final draw list."""
        if self.sort_enabled:
            self._queue.sort(key=lambda s: s.sort_key)
        drawn: List[SpriteInstance] = []
        for sprite in self._queue:
            if visible_check is not None and not visible_check(sprite.position):
                self.stats.culled += 1
                continue
            drawn.append(sprite)
        self.stats.submitted = len(self._queue)
        self.stats.drawn = len(drawn)
        return drawn

    def __len__(self) -> int:
        return len(self._queue)


def build_grid_atlas(name: str, columns: int, rows: int, cell: int = 32) -> SpriteAtlas:
    """Convenience helper defining a uniform grid of frames."""
    atlas = SpriteAtlas(name, page_size=(columns * cell, rows * cell))
    for row in range(rows):
        for col in range(columns):
            atlas.define(f"{row}_{col}", col * cell, row * cell, cell, cell)
    return atlas
