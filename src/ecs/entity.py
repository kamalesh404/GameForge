"""Entity: a lightweight identity object that aggregates typed components."""

from __future__ import annotations

import uuid
from typing import Dict, Iterable, Optional, Set, Type, TypeVar

C = TypeVar("C", bound="Component")  # noqa: F821 - resolved at runtime


class Entity:
    """Unique game object identified by UUID and composed of components."""

    def __init__(self, name: str | None = None, entity_id: uuid.UUID | None = None) -> None:
        self.id: uuid.UUID = entity_id or uuid.uuid4()
        self.name: str = name or f"entity_{self.id.hex[:8]}"
        self.components: Dict[type, object] = {}
        self.tags: Set[str] = set()
        self.alive: bool = True
        self.generation: int = 0

    # -- component management --------------------------------------------------

    def add_component(self, component: object) -> "Entity":
        """Attach *component*, replacing any existing one of the same type."""
        self.components[type(component)] = component
        attach = getattr(component, "on_attach", None)
        if callable(attach):
            attach(self)
        return self

    def get_component(self, component_type: Type[C]) -> Optional[C]:
        """Return the attached component of *component_type* or None."""
        return self.components.get(component_type)  # type: ignore[return-value]

    def require_component(self, component_type: Type[C]) -> C:
        """Like :meth:`get_component` but raises when missing."""
        component = self.get_component(component_type)
        if component is None:
            raise KeyError(f"{self.name} lacks required component {component_type.__name__}")
        return component

    def has_component(self, component_type: Type[C]) -> bool:
        """True when *component_type* is attached."""
        return component_type in self.components

    def remove_component(self, component_type: Type[C]) -> bool:
        """Detach and return whether a component was removed."""
        component = self.components.pop(component_type, None)
        if component is None:
            return False
        detach = getattr(component, "on_detach", None)
        if callable(detach):
            detach(self)
        return True

    @property
    def component_types(self) -> Tuple[type, ...]:
        """Tuple of every attached component's type."""
        return tuple(self.components.keys())

    # -- tags --------------------------------------------------------------------

    def add_tags(self, tags: Iterable[str]) -> "Entity":
        """Union *tags* into this entity's tag set."""
        self.tags.update(tags)
        return self

    def has_tag(self, tag: str) -> bool:
        """True when *tag* is present."""
        return tag in self.tags

    # -- lifecycle -------------------------------------------------------------

    def kill(self) -> None:
        """Mark this entity for destruction by the world."""
        self.alive = False

    def matches_all(self, component_types: Iterable[Type[object]]) -> bool:
        """True when the entity has every listed component type."""
        return all(ct in self.components for ct in component_types)

    def __repr__(self) -> str:
        kinds = ",".join(getattr(t, "__name__", str(t)) for t in self.components)
        return f"<Entity {self.name!r} [{kinds}]>"
