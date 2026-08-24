# Getting Started with GameForge

This guide walks you from a clean checkout to your first running scene.

## Prerequisites

- Python **3.10+** (3.12 recommended)
- `pip` and `venv`
- Optional: a display server for windowed mode; everything works headless too

## Installation

```bash
git clone https://github.com/gameforge/gameforge.git
cd gameforge

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

Verify the install:

```bash
python -c "import src; print(src.version_info())"
# GameForge 0.1.0 (python 3.12.x)
```

## Your First Scene

Create `main.py` in the repository root:

```python
from src.engine.core import Engine, EngineConfig
from src.ecs.component import Sprite, Transform
from src.math.vector import Vector2


def main() -> None:
    engine = Engine(EngineConfig(title="Hello GameForge"))

    # Spawn a player entity composed of components.
    player = engine.world.create_entity(name="player", tags=("hero",))
    player.add_component(Transform(position=Vector2(640, 360)))
    player.add_component(Sprite(texture_path="assets/hero.png", layer=10))

    # React to engine events.
    engine.events.subscribe("engine_shutdown", print)

    engine.run(max_frames=300)   # remove max_frames for a real game loop


if __name__ == "__main__":
    main()
```

Run it:

```bash
python main.py
```

## Adding Gameplay Systems

Systems contain all per-frame logic. Subclass `System`, register it, done:

```python
from src.ecs.system import System
from src.ecs.world import World


class GravitySystem(System):
    def __init__(self) -> None:
        super().__init__(name="gravity", priority=-100)  # runs early

    def update(self, world: World, dt: float) -> None:
        for entity in world.query(Transform):
            tf = entity.require_component(Transform)
            tf.position.y -= 980.0 * dt * -1  # fall toward +y


engine.world.add_system(GravitySystem())
```

## Spinning Up the Physics Sandbox

```python
from src.math.vector import Vector2
from src.physics.collider import AABBCollider
from src.physics.rigidbody import RigidBody
from src.physics.world import PhysicsWorld

world = PhysicsWorld(gravity=Vector2(0, -980))
ball = RigidBody(position=Vector2(0, 500))
world.add_body(ball, CircleCollider(ball.position, radius=16))

for _ in range(120):
    world.step(1 / 60)          # deterministic fixed timestep
print(ball.position)            # ball has fallen and settled
```

## Networking Quick Test

Terminal 1 — start a server:

```python
from src.network.server import GameServer
server = GameServer(port=7777, snapshot_rate_hz=20)
server.start()
input("press Enter to stop\n")
server.stop()
```

Terminal 2 — connect a client:

```python
from src.network.client import GameClient
client = GameClient()
assert client.connect(port=7777)
client.send_chat("hello server")
```

## Next Steps

- Read [architecture.md](architecture.md) for subsystem responsibilities.
- Browse [api_reference.md](api_reference.md) while coding.
- Run `make test` to confirm your environment is healthy.
