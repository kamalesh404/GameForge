"""Scene graph: hierarchical nodes with transform propagation and traversal.

A :class:`Scene` owns a root :class:`SceneNode`; children inherit their
parent's world transform, enabling nested objects such as a turret attached
to a tank hull.
"""

from __future__ import annotations

from typing import Iterator, List, Optional

from src.math.transform import Transform2D, compose_transforms


class SceneNode:
    """A node in the scene graph holding a local transform and children."""

    def __init__(self, name: str, transform: Transform2D | None = None) -> None:
        self.name: str = name
        self.local_transform: Transform2D = transform or Transform2D()
        self.world_transform: Transform2D = Transform2D()
        self.parent: Optional["SceneNode"] = None
        self.children: List["SceneNode"] = []
        self.active: bool = True
        self.tags: List[str] = []

    def add_child(self, child: "SceneNode") -> "SceneNode":
        """Attach *child* beneath this node and return it for chaining."""
        if child.parent is not None:
            child.parent.remove_child(child)
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: "SceneNode") -> bool:
        """Detach *child* from this node. Returns True if it was present."""
        if child in self.children:
            child.parent = None
            self.children.remove(child)
            return True
        return False

    def traverse(self) -> Iterator["SceneNode"]:
        """Depth-first iterator over this node and all descendants."""
        yield self
        for child in self.children:
            yield from child.traverse()

    def find(self, name: str) -> Optional["SceneNode"]:
        """Return the first descendant whose name matches, or None."""
        for node in self.traverse():
            if node.name == name:
                return node
        return None

    @property
    def depth(self) -> int:
        """Number of ancestors above this node."""
        count, node = 0, self.parent
        while node is not None:
            count += 1
            node = node.parent
        return count

    def propagate(self, parent_world: Transform2D | None = None) -> None:
        """Recompute world transforms for this subtree."""
        base = parent_world if parent_world is not None else Transform2D()
        self.world_transform = compose_transforms(base, self.local_transform)
        if not self.active:
            return
        for child in self.children:
            child.propagate(self.world_transform)


class Scene:
    """A named container with a root node and activation state."""

    def __init__(self, name: str = "scene") -> None:
        self.name: str = name
        self.root: SceneNode = SceneNode(f"{name}:root")
        self.active: bool = True

    def spawn(self, name: str, parent: SceneNode | None = None) -> SceneNode:
        """Create a node under *parent* (or root) and return it."""
        node = SceneNode(name)
        (parent or self.root).add_child(node)
        return node

    def find(self, name: str) -> Optional[SceneNode]:
        """Search the whole scene for a node by name."""
        return self.root.find(name)

    def propagate(self) -> None:
        """Refresh every world transform in the scene."""
        if self.active:
            self.root.propagate()

    def nodes(self) -> List[SceneNode]:
        """Return every node in traversal order."""
        return list(self.root.traverse())

    def __len__(self) -> int:
        return len(list(self.root.traverse()))
