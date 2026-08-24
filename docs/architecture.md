# GameForge Architecture

## Design Goals

1. **Determinism** — gameplay runs on a fixed timestep so replays and networked
   simulations stay reproducible.
2. **Composition over inheritance** — behaviour lives in components and
   systems, not deep class hierarchies.
3. **Headless-first** — every subsystem works without a display or audio
   device, enabling CI, bots, and dedicated servers.
4. **Zero hard coupling** — subsystems talk through the `EventBus` and plain
   data structures; each can be used standalone.

## Frame Pipeline

```
poll OS events ─▶ fixed_update (0..N steps @ 60Hz) ─▶ update (variable dt)
                                                        │
                        scene.propagate() ◀─────────────┘
                                │
                          render systems ─▶ present / stats
```

- `Engine.tick()` (`src/engine/core.py`) owns the accumulator that converts
  wall-clock time into deterministic steps.
- Deferred entity destruction is flushed at the top of `World.update` to keep
  iteration safe while systems run.

## Entity Component System

| Piece      | File                 | Responsibility                              |
|------------|----------------------|---------------------------------------------|
| `Entity`   | `src/ecs/entity.py`  | UUID identity + component bag + tags        |
| Components | `src/ecs/component.py` | Pure data: Transform, Sprite, Collider... |
| `System`   | `src/ecs/system.py`  | Pure behaviour, priority-sorted             |
| `World`    | `src/ecs/world.py`   | Storage, queries, scheduling                |

Queries scan live entities and filter by component types plus optional tags.
The registry in `ComponentRegistry` lets tooling enumerate known component
kinds for serialization.

## Physics

`PhysicsWorld.step(dt)` executes four stages:

1. **Sync** collider centers from body positions.
2. **Integrate** all dynamic bodies (semi-implicit Euler, exponential damping).
3. **Broadphase** — `Quadtree` subdivides the world bounds and returns
   overlapping candidate pairs without O(n²) scans.
4. **Narrowphase & solver** — shape dispatch (`detect`) computes contact
   normals/depths; the solver applies restitution impulses plus Baumgarte-style
   positional correction with slop.

Joints (`distance`, `revolute`, `prismatic`) are relaxed iteratively after
contact solving via `solve_joints`.

## Rendering

The renderer is deliberately backend-agnostic:

- `SpriteBatch` collects `SpriteInstance`s per frame, sorts by
  `(layer, z_order)`, culls against the camera rect, and hands back an ordered
  draw list — trivially mapped onto any GPU batcher.
- `Camera` owns world↔screen mapping, smoothed follow, clamped bounds, and
  trauma-squared screen shake.
- `AnimationStateMachine` drives named clips whose keyframes interpolate
  through pluggable easing functions.
- `ParticleSystem` simulates particles with emitter configs plus global force
  fields (wind, vortices, attractors).
- `LightingSystem` composites ambient/directional/point contributions with
  segment-based shadow occluders.

## Networking

```
GameServer                         GameClient
┌──────────────┐   TCP frames     ┌──────────────────┐
│ accept loop  │◀── HELLO ────────│ connect()        │
│ client loops │── WELCOME ─────▶ │ player_id        │
│ snapshot loop│── SNAPSHOT ────▶ │ interpolation    │
│ broadcast()  │◀── INPUT ─────── │ prediction       │
└──────────────┘                  └──────────────────┘
```

Packets use a 24-byte header (`magic`, `flags`, `type`, `seq`, `timestamp`,
`length`), optional zlib compression, and a trailing CRC32. The client renders
entities ~100 ms in the past by interpolating between buffered snapshots while
predicting its own avatar locally and reconciling on drift.

## Error Handling Philosophy

Subsystems fail loudly at construction time (bad radii, malformed packets) but
degrade gracefully at runtime: unknown packet types are ignored, missing Lua
falls back to stub hooks, and audio voice exhaustion returns `None`.
