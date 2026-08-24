"""Built-in component types composing standard gameplay behaviour."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from src.math.vector import Vector2
from src.physics.collider import BaseCollider

if TYPE_CHECKING:  # pragma: no cover
    from src.ecs.entity import Entity


class Component(ABC):
    """Base contract for every ECS component."""

    enabled: bool = True

    def on_attach(self, entity: "Entity") -> None:
        """Called once when added to *entity*."""

    def on_detach(self, entity: "Entity") -> None:
        """Called once before removal from *entity*."""


@dataclass
class Transform(Component):
    """World placement: translation, rotation, and scale."""

    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    rotation_degrees: float = 0.0
    scale: Vector2 = field(default_factory=lambda: Vector2(1.0, 1.0))

    def translate(self, offset: Vector2) -> None:
        """Move by *offset* in world space."""
        self.position = self.position + offset

    def forward(self) -> Vector2:
        """Unit vector pointing along current rotation."""
        return Vector2.from_angle(self.rotation_degrees)


@dataclass
class Sprite(Component):
    """Renderable image reference consumed by the renderer."""

    texture_path: str = ""
    layer: int = 0
    z_order: float = 0.0
    tint: Tuple[int, int, int, int] = (255, 255, 255, 255)
    flip_x: bool = False
    flip_y: bool = False
    visible: bool = True
    pivot: Vector2 = field(default_factory=lambda: Vector2(0.5, 0.5))


@dataclass
class Collider(Component):
    """Physics shape wrapper marking an entity collidable."""

    shape: BaseCollider
    is_trigger: bool = False
    friction: float = 0.4
    restitution: float = 0.1
    offset: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))

    def world_shape_center(self, entity_position: Vector2) -> Vector2:
        """Shape center translated by the owning entity's position."""
        return entity_position + self.offset


BodyType = str  # one of "static", "kinematic", "dynamic"


@dataclass
class RigidBody(Component):
    """Newtonian motion properties for physics integration."""

    mass: float = 1.0
    velocity: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    gravity_scale: float = 1.0
    body_type: BodyType = "dynamic"
    linear_damping: float = 0.05
    is_sensor: bool = False
    awake: bool = True

    def is_dynamic(self) -> bool:
        """True only for gravity/mass-affected dynamic bodies."""
        return self.body_type == "dynamic"


@dataclass
class Script(Component):
    """Binds gameplay callbacks or a script file to an entity."""

    source_path: str = ""
    on_update: Optional[Callable[[object, float], None]] = None
    on_start: Optional[Callable[[object], None]] = None
    started: bool = False
    locals: List[str] = field(default_factory=list)


@dataclass
class Audio(Component):
    """Attaches a looping or one-shot sound to spatial position."""

    sound_name: str = ""
    volume: float = 1.0
    pitch: float = 1.0
    loop: bool = False
    autoplay: bool = False
    max_distance: float = 800.0


class ComponentRegistry:
    """Utility cataloguing known component classes for tooling/serializers."""

    _known: List[type] = []

    @classmethod
    def register(cls, component_type: type) -> type:
        """Add *component_type* to the registry (usable as decorator)."""
        if component_type not in cls._known:
            cls._known.append(component_type)
        return component_type

    @classmethod
    def known(cls) -> List[type]:
        """Return registered component classes in registration order."""
        return list(cls._known)


for _builtin in (Transform, Sprite, Collider, RigidBody, Script, Audio):
    ComponentRegistry.register(_builtin)
