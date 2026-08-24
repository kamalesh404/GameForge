"""Tests for engine initialization, event bus, and the game loop."""

import time

import pytest

from src.engine.assets import AssetCache, PlaceholderTexture, TextureLoader
from src.engine.core import Engine, EngineConfig, EventBus
from src.engine.scene import Scene, SceneNode
from src.engine.window import Window, WindowConfig


class TestEventBus:
    def test_subscribe_and_post(self) -> None:
        bus = EventBus()
        seen = []
        bus.subscribe("damage", lambda data: seen.append(data))
        bus.post("damage", {"amount": 12})
        assert seen == [{"amount": 12}]

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        calls = []
        token = bus.subscribe("tick", calls.append)
        assert bus.unsubscribe(token) is True
        bus.post("tick", 1)
        assert calls == []

    def test_deferred_queueing(self) -> None:
        bus = EventBus()
        hits = []
        bus.subscribe("hit", lambda d: hits.append(d))
        bus.deferred = True
        bus.post("hit", "a")
        bus.post("hit", "b")
        assert hits == []  # nothing dispatched yet
        pumped = bus.pump()
        assert pumped == 2 and len(hits) == 2


class TestWindow:
    def test_open_close_cycle(self) -> None:
        win = Window(WindowConfig(title="t", width=800, height=600))
        assert win.open() is True
        assert win.is_open
        win.close()
        assert not win.is_open

    def test_resize_notifies_callbacks(self) -> None:
        win = Window()
        sizes = []
        win.add_resize_callback(lambda w, h: sizes.append((w, h)))
        win.resize(1920, 1080)
        assert sizes == [(1920, 1080)]

    def test_fullscreen_toggle_picks_mode(self) -> None:
        win = Window(WindowConfig(width=640, height=480))
        assert win.toggle_fullscreen() is True
        best = max(win.display_modes, key=lambda m: m.width * m.height)
        assert (win.width, win.height) == (best.width, best.height)

    def test_aspect_ratio(self) -> None:
        win = Window(WindowConfig(width=1280, height=720))
        assert abs(win.aspect_ratio - 16 / 9) < 1e-6


class TestSceneGraph:
    def test_hierarchy_and_traversal(self) -> None:
        scene = Scene("demo")
        parent = scene.spawn("tank")
        turret = scene.spawn("turret", parent=parent)
        assert turret.parent is parent
        names = [n.name for n in scene.nodes()]
        assert names == ["demo:root", "tank", "turret"]

    def test_find_missing_returns_none(self) -> None:
        assert Scene().find("ghost") is None

    def test_world_transform_composition(self) -> None:
        root = SceneNode("root")
        child = SceneNode("child")
        root.add_child(child)
        from src.math.transform import Transform2D

        root.local_transform.position.x = 10.0
        child.local_transform.position.x = 5.0
        root.propagate()
        assert child.world_transform.position.x == pytest.approx(15.0)


class TestEngineLoop:
    def test_engine_runs_frames(self) -> None:
        engine = Engine(EngineConfig(headless=True))
        engine.run(max_frames=3)
        assert engine.stats.frame_count >= 3
        assert not engine.running

    def test_events_flow_through_loop(self) -> None:
        engine = Engine(EngineConfig(headless=True))
        received = []
        engine.events.subscribe("engine_shutdown", received.append)
        engine.run(max_frames=1)
        assert received and received[0]["frames"] >= 1

    def test_fps_statistics_populated(self) -> None:
        engine = Engine(EngineConfig(headless=True))
        engine.initialize()
        for _ in range(5):
            engine.tick()
            time.sleep(0.001)
        assert engine.stats.fps > 0
        assert len(engine.stats.history) == 5


class TestAssets:
    def test_cache_hit_and_miss_counters(self) -> None:
        cache = AssetCache(max_entries=4)
        cache.put("a", 1)
        assert cache.get("a") == 1
        assert cache.get("zz") is None
        assert cache.stats["hits"] == 1 and cache.stats["misses"] == 1

    def test_lru_eviction(self) -> None:
        cache = AssetCache(max_entries=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.get("a") is None and len(cache) == 2

    def test_texture_loader_placeholder(self, tmp_path) -> None:
        tex_path = tmp_path / "hero.png"
        tex_path.write_bytes(b"\x89PNG fake")
        texture = TextureLoader().load(tex_path)
        assert isinstance(texture, PlaceholderTexture)
        assert texture.path.name == "hero.png"
