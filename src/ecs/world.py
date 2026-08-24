"""The ECS World: entity storage, queries, and system scheduling."""

from __future__ import annotations

import uuid
from typing import Dict, Iterable, List, Optional, Set, Type, TypeVar, Union

from src.ecs.entity import Entity
from src.ecs.system import SystemManager

T = TypeVar("T")


class World:
    """Container for entities and the systems that mutate them each frame."""

    def __init__(self) -> None:
        self.entities: Dict[uuid.UUID, Entity] = {}
        self.systems: SystemManager = SystemManager()
        self.pending_destroy: Set[uuid.UUID] = set()
        self.on_entity_created = None  # Optional callback(Entity)
        self.on_entity_destroyed = None  # Optional callback(Entity)
        self.time_elapsed: float = 0.0

    # -- entity lifecycle ------------------------------------------------------

    def create_entity(self, *components: object, name: str | None = None,
                      tags: Iterable[str] | None = None) -> Entity:
        """Spawn an :class:`Entity`, optionally seeding components/tags."""
        entity = Entity(name=name)
        for component in components:
            entity.add_component(component)
        if tags:
            entity.add_tags(tags)
        self.entities[entity.id] = entity
        if self.on_entity_created is not None:
            self.on_entity_created(entity)
        return entity

    def destroy_entity(self, target: Union[Entity, uuid.UUID]) -> bool:
        """Remove *target* immediately and notify listeners."""
        entity_id = target.id if isinstance(target, Entity) else target
        entity = self.entities.pop(entity_id, None)
        if entity is None:
            return False
        entity.kill()
        self.pending_destroy.discard(entity_id)
        if self.on_entity_destroyed is not None:
            self.on_entity_destroyed(entity)
        return True

    def defer_destroy(self, target: Union[Entity, uuid.UUID]) -> None:
        """Queue destruction until the next :meth:`flush`."""
        entity_id = target.id if isinstance(target, Entity) else target
        if entity_id in self.entities:
            self.pending_destroy.add(entity_id)

    def flush(self) -> int:
        """Process deferred destructions; returns how many were removed."""
        ids = list(self.pending_destroy)
        removed = sum(1 for eid in ids if self.destroy_entity(eid))
        return removed

    def get_entity(self, entity_id: uuid.UUID) -> Optional[Entity]:
        """Look up a live entity by id."""
        return self.entities.get(entity_id)

    def find_by_name(self, name: str) -> Optional[Entity]:
        """First live entity whose name matches."""
        for entity in self.entities.values():
            if entity.name == name:
                return entity
        return None

    # -- queries -----------------------------------------------------------------

    def query(self, *component_types: Type[object], tags: Iterable[str] | None = None) -> List[Entity]:
        """Entities holding every listed component (and optionally all tags)."""
        required_tags = set(tags or ())
        results: List[Entity] = []
        for entity in list(self.entities.values()):
            if not entity.alive or not entity.matches_all(component_types):
                continue
            if required_tags and not required_tags.issubset(entity.tags):
                continue
            results.append(entity)
        return results

    def query_tag(self, tag: str) -> List[Entity]:
        """All entities carrying *tag*."""
        return [e for e in self.entities.values() if e.alive and e.has_tag(tag)]

    @property
    def entity_count(self) -> int:
        """Number of live entities."""
        return len(self.entities)

    # -- frame pipeline -------------------------------------------------------------

    def add_system(self, system) -> object:
        """Register a system with this world's manager."""
        from src.ecs.system import System

        assert isinstance(system, System)
        return self.systems.register(system, world=self)

    def fixed_update(self, dt: float) -> None:
        """Deterministic physics-rate step."""
        self.systems.fixed_update(self, dt)

    def update(self, dt: float) -> None:
        """Variable-timestep step followed by deferred cleanup."""
        self.time_elapsed += dt
        self.flush()
        self.systems.update(self, dt)

    def render(self) -> None:
        """Execute render-phase systems in priority order."""
        self.systems.render(self)

    def clear(self) -> None:
        """Remove every entity but keep registered systems."""
        self.entities.clear()
        self.pending_destroy.clear()

    def __len__(self) -> int:
        return len(self.entities)
