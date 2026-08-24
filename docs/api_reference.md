# GameForge API Reference

Condensed reference for the most-used entry points. All classes live under
the `src` package.

## Engine (`src.engine.core`)

| Symbol | Signature | Notes |
|--------|-----------|-------|
| `Engine` | `Engine(config: EngineConfig = None)` | Owns window, world, scene, stats |
| `Engine.tick` | `() -> float` | Runs one frame; returns delta seconds |
| `Engine.run` | `(max_frames: int \| None) -> None` | Blocking loop with graceful shutdown |
| `EventBus.subscribe` | `(event_type: str, handler) -> int` | Returns unsubscribe token |
| `EventBus.post` | `(event_type: str, data: Any = None) -> None` | Sync or deferred dispatch |
| `EngineConfig` | dataclass | `title`, `width`, `height`, `target_fps`, `fixed_timestep`, `headless` |

## ECS (`src.ecs`)

```python
world.create_entity(Transform(), Sprite(), tags=("enemy",)) -> Entity
world.query(Transform, Sprite, tags=None) -> list[Entity]
world.destroy_entity(entity_or_id) -> bool      # immediate
world.defer_destroy(entity_or_id) -> None       # flushed in update()
entity.add_component(comp) -> Entity            # chainable
entity.require_component(Transform) -> Transform  # raises KeyError
```

Built-in components: `Transform`, `Sprite`, `Collider`, `RigidBody`,
`Script`, `Audio`. Systems implement `update` / `fixed_update` / `render`;
lower `priority` values run first.

## Math (`src.math`)

- `Vector2` — full operator suite, `dot`, `cross`, `rotated(degrees)`,
  `lerp`, `reflect(normal)`, constants `ZERO/ONE/UNIT_X/UNIT_Y`.
- `Vector3`, `Vector4` — 3D math and RGBA helpers.
- `Transform2D.apply_point(p)` — affine point transform;
  `compose_transforms(parent_world, local)` for hierarchies.
- `SeededRandom(seed)` — reproducible streams; `ValueNoise.fbm(x, y, octaves)`
  for procedural content.

## Physics (`src.physics`)

```python
pw = PhysicsWorld(gravity=Vector2(0, -980))
binding = pw.add_body(body, shape, sensor_only=False)
contacts = pw.step(1 / 60)          # returns resolved contact count
solve_joints([joint], iterations=3) # post-solve constraint relaxation
```

Shapes: `AABBCollider(center, half_extents)`,
`CircleCollider(center, radius)`,
`PolygonCollider(center, vertices)` (convex, SAT-based).
Joints: `DistanceJoint`, `RevoluteJoint(anchor)`, `PrismaticJoint(axis_degrees,
min_limit, max_limit)`.

## Renderer (`src.renderer`)

- `Camera(viewport_w, viewport_h)` — `follow(target, dt)`, `add_trauma(x)`,
  `world_to_screen(p)`, `screen_to_world(p)`, `visible_world_rect`.
- `SpriteBatch` — `begin()` → `draw(instance)` → `flush(visible_check)`.
- `AnimationStateMachine` — `add_state(name, state)`, `play(name)`,
  `update(dt) -> sampled_value`.
- `ParticleSystem` — `add_emitter(cfg)`, `burst(origin, count)`, `update(dt)`.
- `LightingSystem.illuminate(point) -> (level, contributing_lights)`.

## Audio (`src.audio`)

```python
am = AudioManager(master_volume=0.9)
am.library.register(Sound("laser", duration=0.4))
sound = am.play("laser", channel_name="sfx", world_position=Vector2(300, 0))
am.update(dt)                       # advances fades and playback heads
```

Spatial gain and stereo pan derive from the shared `Listener`.

## Input (`src.input`)

- `InputManager.bind_action("jump", keys=[32])` then query
  `is_action_active("jump")` or edge-triggered `action_just_pressed("jump")`.
- Call `end_frame()` once per frame to reset edge states.
- `GamepadManager.on_connect(index)` returns a `Gamepad`; use
  `stick_vector()` (radial dead zone applied) and `start_rumble(lo, hi, secs)`.

## UI (`src.ui`)

Widgets: `Button`, `Label`, `Panel`. Route events through `UIManager`:

```python
ui = UIManager()
btn = ui.add(Button("play", text="Play"))
btn.on_click(lambda b: print("clicked!"))
consumed = ui.process_input(input_manager)
```

`cycle_focus()` implements Tab navigation across focusable widgets.

## Networking (`src.network`)

Server:

```python
server = GameServer(port=7777, snapshot_rate_hz=20)
server.on_packet = lambda client, pkt: ...
port = server.start()   # port 0 binds an ephemeral port
server.stop()
```

Client:

```python
client = GameClient()
client.connect(port=7777)
client.send_chat("hi")
snap_pos = client.interpolated_position(entity_id=3)
```

Packets are framed, CRC-checked, optionally compressed; see
`Packet.serialize/deserialize` and the `PacketType` enum.

## Scripting (`src.scripting`)

- `LuaBridge.load_script(name, source)` then `.call(name, hook, *args)`
  (real Lua when `lupa` is installed; stub otherwise).
- `ScriptEventQueue.emit(name, payload)` + `process(limit)` deliver bounded,
  ordered gameplay events to script handlers.
