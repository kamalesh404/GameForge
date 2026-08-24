"""Asset pipeline: pluggable loaders, LRU caching, reference counting.

The :class:`ResourceManager` maps file extensions to loader callables, caches
results in an :class:`AssetCache`, and supports hot-reload invalidation.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol


class Loader(Protocol):
    """Anything that can turn a path into an asset instance."""

    def load(self, path: Path) -> Any:  # pragma: no cover - protocol
        ...


class PlaceholderTexture:
    """Headless stand-in for a decoded image; records size and source."""

    def __init__(self, path: Path, width: int = 32, height: int = 32) -> None:
        self.path: Path = path
        self.width: int = width
        self.height: int = height

    def __repr__(self) -> str:
        return f"PlaceholderTexture({self.path.name!r}, {self.width}x{self.height})"


class TextureLoader:
    """Default image loader returning placeholder textures when headless."""

    def load(self, path: Path) -> PlaceholderTexture:
        if not path.exists():
            raise FileNotFoundError(f"texture not found: {path}")
        return PlaceholderTexture(path)


class AudioLoader:
    """Loads sound files into lightweight descriptors."""

    def load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"audio not found: {path}")
        return {"path": str(path), "channels": 2, "sample_rate": 44100}


class AssetCache:
    """An LRU cache that also tracks hit/miss statistics."""

    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries: int = max(1, max_entries)
        self._entries: OrderedDict[str, Any] = OrderedDict()
        self.hits: int = 0
        self.misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        """Return the cached asset for *key*, refreshing recency."""
        if key not in self._entries:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return self._entries[key]

    def put(self, key: str, value: Any) -> None:
        """Insert or refresh *key*, evicting the least-recent entry if full."""
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Drop *key* from the cache; returns True if it existed."""
        return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        """Empty the cache and reset statistics."""
        self._entries.clear()
        self.hits = self.misses = 0

    @property
    def stats(self) -> Dict[str, int]:
        """Snapshot of cache performance counters."""
        return {"hits": self.hits, "misses": self.misses, "size": len(self._entries)}

    def __len__(self) -> int:
        return len(self._entries)


class ResourceManager:
    """Central registry binding extensions to loaders with shared caching."""

    def __init__(self, root: str | Path = ".", cache_size: int = 256) -> None:
        self.root: Path = Path(root)
        self.cache = AssetCache(cache_size)
        self._loaders: Dict[str, Loader] = {
            ".png": TextureLoader(),
            ".jpg": TextureLoader(),
            ".wav": AudioLoader(),
            ".ogg": AudioLoader(),
        }
        self._refcounts: Dict[str, int] = {}

    def register_loader(self, extension: str, loader: Loader) -> None:
        """Bind *loader* to files ending in *extension* (case-insensitive)."""
        self._loaders[extension.lower().lstrip(".")] = loader

    def resolve(self, relative: str) -> Path:
        """Resolve *relative* against the resource root."""
        return (self.root / relative).resolve()

    def load(self, resource_path: str) -> Any:
        """Load (or fetch cached) asset at *resource_path*."""
        path = self.resolve(resource_path)
        key = str(path).lower()
        cached = self.cache.get(key)
        if cached is not None:
            self.retain(key)
            return cached
        ext = path.suffix.lower().lstrip(".")
        loader = self._loaders.get(ext)
        if loader is None:
            raise LookupError(f"no loader registered for '{ext}' files")
        asset = loader.load(path)
        self.cache.put(key, asset)
        self.retain(key)
        return asset

    def retain(self, key: str) -> int:
        """Increment and return the reference count for *key*."""
        self._refcounts[key] = self._refcounts.get(key, 0) + 1
        return self._refcounts[key]

    def release(self, resource_path: str) -> int:
        """Decrement refcount; unload the asset when it reaches zero."""
        path = self.resolve(resource_path)
        key = str(path).lower()
        count = max(0, self._refcounts.get(key, 0) - 1)
        if count == 0:
            self._refcounts.pop(key, None)
            self.cache.invalidate(key)
        else:
            self._refcounts[key] = count
        return count

    @property
    def stats(self) -> Dict[str, int]:
        """Snapshot of cache performance counters."""
        return {"hits": self.cache.hits, "misses": self.cache.misses, "size": len(self.cache)}
