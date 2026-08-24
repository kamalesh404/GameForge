"""Tests for entities, components, systems, and the ECS world."""

import pytest

from src.ecs.component import (
    Audio,
    Collider,
    ComponentRegistry,
    RigidBody,
    Script,
    Sprite,
    Transform,
)
from src.ecs.entity import Entity
from src.ecs.system import System
from src.ecs.world import World
from src.math.vector import Vector2
from src.physics.collider import CircleCollider


class CounterSystem(System):
    def __init__(self) -> None:
        super().__init__(name="counter", priority=5)
        self.updates = 0
        self.fixed_updates = 0

    def update(self, world: World, dt: float) -> None:
        self.updates += 1

    def fixed_update(self, world: World, dt: float) -> None:
        self.fixed_updates += 1


class TestEntity:
    def test_unique_ids_and_names(self) -> None:
        a, b = Entity("a"), Entity("b")
        assert a.id != b.id and a.name == "a"

    def test_component_add_get_remove(self) -> None:
        e = Entity()
        e.add_component(Transform(position=Vector2(1, 2)))
        assert e.has_component(Transform)
        t = e.require_component(Transform)
        assert (t.position.x, t.position.y) == (1, 2)
        assert e.remove_component(Transform) is True
        with pytest.raises(KeyError):
            e.require_component(Transform)

    def test_tags(self) -> None:
        e = Entity().add_tags(("enemy", "elite"))
        assert e.has_tag("enemy") and not e.has_tag("player")

    def test_matches_all(self) -> None:
        e = Entity()
        e.add_component(Transform()).add_component(Sprite(texture_path="x.png"))
        assert e.matches_all([Transform, Sprite])
        assert not e.matches_all([Transform, Collider])


class TestWorld:
    def test_create_and_query(self) -> None:
        world = World()
        world.create_entity(Transform(), Sprite(), tags=("hero",))
        world.create_entity(Transform())
        hits = world.query(Transform, Sprite)
        assert len(hits) == 1 and hits[0].has_tag("hero")

    def test_destroy_is_immediate_and_deferred_modes(self) -> None:
        world = World()
        e1 = world.create_entity(name="one")
        e2 = world.create_entity(name="two")
        assert world.destroy_entity(e1) is True
        assert world.get_entity(e1.id) is None
        world.defer_destroy(e2)
        assert world.entity_count == 1  # e2 still live, just queued
        world.update(0.016)  # flush happens inside update
        assert world.entity_count == 0

    def test_lifecycle_callbacks_fire(self) -> None:
        world = World()
        created, destroyed = [], []
        world.on_entity_created = created.append
        world.on_entity_destroyed = destroyed.append
        e = world.create_entity()
        world.destroy_entity(e)
        assert created == [e] and destroyed == [e]

    def test_query_by_tag(self) -> None:
        world = World()
        world.create_entity(tags=("ui",))
        world.create_entity(tags=("gameplay",))
        assert len(world.query_tag("ui")) == 1


class TestSystems:
    def test_priority_ordering_pipeline(self) -> None:
        world = World()
        order = []

        class NamedSystem(System):
            def __init__(self, name: str, prio: int) -> None:
                super().__init__(name=name, priority=prio)

            def update(self, w: World, dt: float) -> None:
                order.append(self.name)

        world.add_system(NamedSystem("late", 50))
        world.add_system(NamedSystem("early", -10))
        world.add_system(NamedSystem("middle", 0))
        world.update(0.016)
        assert tuple(order) == ("early", "middle", "late")
        assert world.systems.describe_pipeline() == ("early", "middle", "late")

    def test_fixed_vs_variable_phases(self) -> None:
        world = World()
        counter = world.add_system(CounterSystem())
        world.fixed_update(1 / 60)
        world.update(0.016)
        assert counter.fixed_updates == 1 and counter.updates == 1

    def test_disabled_system_skipped(self) -> None:
        world = World()
        sysm = world.add_system(CounterSystem())
        sysm.enabled = False
        world.update(0.016)
        assert sysm.updates == 0

    def test_duplicate_registration_rejected(self) -> None:
        world = World()
        first = CounterSystem()
        world.systems.register(first, world=world)
        with pytest.raises(ValueError):
            world.systems.register(CounterSystem())

    def test_unregister(self) -> None:
        manager = __import__("src.ecs.system", fromlist=["SystemManager"]).SystemManager()
        s = CounterSystem()
        manager.register(s)
        assert manager.unregister("counter") is True


class TestComponents:
    def test_builtin_registry_contains_builtins(self) -> None:
        names = {c.__name__ for c in ComponentRegistry.known()}
        assert {"Transform", "Sprite", "Collider", "RigidBody", "Script", "Audio"} <= names

    def test_attach_detach_hooks(self) -> None:
        seen = []

        class Hooky(Sprite):
            def on_attach(self, entity):
                seen.append(("attach", entity.name))

            def on_detach(self, entity):
                seen.append(("detach", entity.name))

        e = Entity("hooky")
        comp = Hooky(texture_path="a.png")
        e.add_component(comp)
        e.remove_component(Hooky)
        assert ("attach", "hooky") in seen and ("detach", "hooky") in seen

    def test_rigidbody_dynamic_flag(self) -> None:
        body = RigidBody(body_type="static")
        assert not body.is_dynamic()

    def test_collider_world_center_offset(self) -> None:
        col = Collider(shape=CircleCollider(Vector2(0, 0), radius=8), offset=Vector2(4, 4))
        assert col.world_shape_center(Vector2(10, 10)) == Vector2(14, 14)


def test_script_audio_defaults() -> None:
    script = Script(source_path="boss.lua")
    audio = Audio(sound_name="explosion", autoplay=True)
    assert script.source_path.endswith(".lua") and audio.autoplay
