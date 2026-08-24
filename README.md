# GameForge

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-passing-success)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

GameForge is a modular, cross-platform 2D game engine written in pure Python.
It ships with an entity-component-system core, a layered renderer, a rigid-body
physics solver, spatial audio, UI widgets, networking, and a scripting bridge —
everything a small studio needs to prototype and ship 2D games.

## Features

- **Engine Core** — deterministic fixed-timestep game loop, delta time, FPS
  statistics, and a global event bus for decoupled subsystem communication.
- **ECS Architecture** — UUID-based entities, typed components, priority-sorted
  systems, deferred destruction, and fast component queries.
- **Rendering** — sprite batching with atlas support, cameras with follow /
  shake / zoom, keyframe animation state machines, GPU-friendly particle
  emitters, and a composited lighting model.
- **Physics** — AABB / circle / polygon (SAT) collision detection, quadtree
  broadphase, impulse-based resolution, and distance / revolute / prismatic
  joints.
- **Audio** — channel mixer, fade in/out, looping, and listener-relative
  spatial panning.
- **Scripting** — optional Lua bridge (via `lupa`) plus a queue-backed script
  event system for gameplay logic.
- **Input** — rebindable action mappings for keyboard, mouse, and gamepads
  with radial dead zones and rumble support.
- **UI** — retained-mode widget toolkit: buttons, labels, panels, focus
  traversal, z-ordered hit testing.
- **Networking** — TCP client/server with framed, CRC-checked, optionally
  compressed packets, snapshot interpolation, and client-side prediction.
- **Math** — Vector2/3/4, affine transforms, seeded RNG, and value noise.

## Architecture

```
┌──────────────────────────── Engine ────────────────────────────┐
│                                                                │
│  ┌──────┐   ┌─────────┐   ┌─────────┐   ┌────────┐   ┌──────┐  │
│  │ Window│──▶│  Scene  │──▶│   ECS   │──▶│Systems │◀──│Events│  │
│  └──────┘   └─────────┘   └────┬────┘   └───┬────┘   └──────┘  │
│                                │             │                  │
│      ┌───────────┬─────────────┼─────────────┼──────────┐       │
│      ▼           ▼             ▼             ▼          ▼       │
│  Renderer     Physics        Audio         Input       Script    │
│      ▲                                                       │    │
│      └───────────────────── UI ◀─────────────────────────────┘   │
│                                                                  │
│              Math ◀──── shared by every subsystem                │
└──────────────────────── Network (optional) ──────────────────────┘
```

Data flows one way per frame: input is polled, gameplay systems mutate the ECS
world inside the fixed timestep, physics steps the simulation, and the renderer
draws the resulting state through the active camera.

## Installation

```bash
git clone https://github.com/gameforge/gameforge.git
cd gameforge
pip install -e ".[dev]"
```

## Quick Start

```python
from src.engine.core import Engine, EngineConfig
from src.ecs.world import World
from src.ecs.entity import Entity
from src.ecs.component import Transform, Sprite

engine = Engine(EngineConfig(title="My Game", width=1280, height=720))

player = engine.world.create_entity(name="player")
player.add_component(Transform(position=(640, 360)))
player.add_component(Sprite(texture_path="assets/player.png", layer=1))

engine.run(max_frames=600)  # run headlessly or until window closes
```

Run the test suite:

```bash
make test
```

## Project Layout

| Path            | Description                              |
|-----------------|------------------------------------------|
| `src/engine`    | Game loop, window, scenes, assets        |
| `src/ecs`       | Entities, components, systems, world     |
| `src/renderer`  | Sprites, camera, animation, FX, lighting |
| `src/physics`   | Colliders, rigid bodies, joints, solver  |
| `src/audio`     | Mixer, channels, spatial audio           |
| `src/scripting` | Lua bridge, script events                |
| `src/input`     | Keyboard/mouse actions, gamepads         |
| `src/ui`        | Retained-mode widget toolkit             |
| `src/math`      | Vectors, transforms, noise               |
| `src/network`   | Server, client, packet protocol          |

## Documentation

- [Getting Started](docs/getting_started.md)
- [Architecture](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Contributing](docs/contributing.md)

## License

MIT — see [LICENSE](LICENSE).
