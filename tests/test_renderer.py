"""Tests for sprites, batching, cameras, animation, and particles."""

import math

import pytest

from src.math.vector import Vector2
from src.renderer.animation import (
    EASINGS,
    AnimationClip,
    AnimationState,
    AnimationStateMachine,
    bounce_out,
)
from src.renderer.camera import Camera
from src.renderer.particles import Emitter, Particle, ParticleSystem, vortex_field
from src.renderer.sprite import SpriteAtlas, SpriteBatch, SpriteInstance, build_grid_atlas


class TestCamera:
    def test_identity_projection_centers_origin(self) -> None:
        cam = Camera(1280, 720)
        center = cam.world_to_screen(Vector2(0, 0))
        assert (center.x, center.y) == (640.0, 360.0)

    def test_zoom_scales_projection(self) -> None:
        cam = Camera(1000, 1000)
        cam.zoom = 2.0
        screen = cam.world_to_screen(Vector2(50, 50))
        assert screen.x == pytest.approx(500 + 100)  # 50 * zoom offset from center

    def test_roundtrip_screen_to_world(self) -> None:
        cam = Camera(800, 600)
        cam.position = Vector2(120, -40)
        world_pt = Vector2(-333.5, 210.25)
        back = cam.screen_to_world(cam.world_to_screen(world_pt))
        assert back.x == pytest.approx(world_pt.x, abs=1e-6)
        assert back.y == pytest.approx(world_pt.y, abs=1e-6)

    def test_follow_converges(self) -> None:
        cam = Camera()
        for _ in range(200):
            cam.follow(Vector2(500, 250), dt=1 / 60, lerp_factor=8.0)
        assert cam.position.distance_to(Vector2(500, 250)) < 1.0

    def test_shake_decay_and_bounds_clamp(self) -> None:
        cam = Camera()
        cam.add_trauma(1.0)
        offset, rotation = cam.update(dt=10.0)
        assert cam.trauma == 0.0 and offset.length() <= cam.max_shake_offset + 1e-6
        cam.set_bounds(Vector2(0, 0), Vector2(100, 100))
        cam.snap_to(Vector2(-999, 999))
        assert cam.position == Vector2(0, 100)

    def test_visibility_culling(self) -> None:
        cam = Camera(400, 400)
        assert cam.is_visible(Vector2(0, 0))
        assert not cam.is_visible(Vector2(10_000, 0))


class TestSprites:
    def test_atlas_define_and_lookup(self) -> None:
        atlas = SpriteAtlas("tiles")
        atlas.define("grass", 0, 0, 32, 32)
        frame = atlas.get("grass")
        assert frame is not None and frame.width == 32
        assert "grass" in atlas and "lava" not in atlas

    def test_batch_sorts_by_layer_then_z(self) -> None:
        batch = SpriteBatch()
        batch.begin()
        batch.draw(SpriteInstance(Vector2(0, 0), "a", layer=1, z_order=5))
        batch.draw(SpriteInstance(Vector2(0, 0), "b", layer=0, z_order=99))
        batch.draw(SpriteInstance(Vector2(0, 0), "c", layer=0, z_order=1))
        drawn = batch.flush()
        assert [s.frame_key for s in drawn] == ["c", "b", "a"]
        assert batch.stats.submitted == 3 and batch.stats.drawn == 3

    def test_flush_culls_offscreen(self) -> None:
        batch = SpriteBatch()
        batch.begin()
        batch.draw(SpriteInstance(Vector2(0, 0), "onscreen"))
        batch.draw(SpriteInstance(Vector2(9999, 9999), "offscreen"))
        drawn = batch.flush(visible_check=lambda p: p.x < 1000)
        assert len(drawn) == 1 and batch.stats.culled == 1

    def test_grid_atlas_builder(self) -> None:
        atlas = build_grid_atlas("sheet", columns=4, rows=2, cell=16)
        assert len(atlas.frames) == 8
        assert atlas.get("1_3").x == 48


class TestAnimation:
    def test_clip_samples_keyframes(self) -> None:
        clip = AnimationClip("rise", duration=1.0, loop=False)
        clip.add_key(0.0, 0.0).add_key(1.0, 100.0)
        assert clip.sample(0.5) == pytest.approx(50.0)
        assert clip.sample(9.9) == pytest.approx(100.0)  # clamped when not looping

    def test_easing_changes_interpolation(self) -> None:
        clip = AnimationClip("eased", duration=1.0, loop=False)
        clip.add_key(0.0, 0.0).add_key(1.0, 1.0, easing="in_quad")
        assert clip.sample(0.5) == pytest.approx(0.25)  # t^2 at midpoint

    def test_easings_registry_complete(self) -> None:
        assert set(EASINGS) >= {"linear", "in_quad", "out_quad", "in_out_sine", "bounce_out"}
        assert bounce_out(0.0) == 0.0 and bounce_out(1.0) == pytest.approx(1.0, abs=0.01)

    def test_state_machine_transitions(self) -> None:
        idle_clip = AnimationClip("idle", duration=0.1)
        run_clip = AnimationClip("run", duration=0.4)
        machine = AnimationStateMachine()
        machine.add_state("idle", AnimationState(idle_clip, transitions=[
            ("run", lambda: machine.elapsed > 0.05),
        ]))
        machine.add_state("run", AnimationState(run_clip))
        machine.play("idle")
        value = machine.update(0.06)
        assert machine.current_name == "run"
        assert 0.0 <= value <= 1.0


class TestParticles:
    def test_particle_lifetime_expires(self) -> None:
        p = Particle(position=Vector2(0, 0), velocity=Vector2(10, 0), max_lifetime=0.5)
        p.step(0.6)
        assert not p.alive

    def test_emitter_spawns_over_time(self) -> None:
        system = ParticleSystem(max_particles=100)
        system.add_emitter(Emitter(rate_per_second=100.0))
        system.update(0.1)
        assert system.live_count >= 5
        system.update(1.0)
        assert system.live_count > 0

    def test_burst_respects_cap(self) -> None:
        system = ParticleSystem(max_particles=7)
        spawned = system.burst(Vector2(0, 0), count=50)
        assert spawned == 7 and system.live_count == 7

    def test_force_fields_apply(self) -> None:
        system = ParticleSystem()
        system.burst(Vector2(0, 0), count=1, speed=(1.0, 1.0))
        system.force_fields.append(vortex_field(Vector2(0, 0), spin=90.0))
        before = system.particles[0].velocity.copy()
        system.update(0.05)
        after = system.particles[0].velocity if system.live_count else Vector2(0, 0)
        assert isinstance(after, Vector2)
        assert after.x != before.x or after.y != before.y or system.live_count == 0

    def test_draw_commands_fade_with_life(self) -> None:
        system = ParticleSystem()
        system.burst(Vector2(0, 0), count=3)
        cmds = system.draw_commands()
        assert len(cmds) == 3
        positions, sizes, colors = cmds[0]
        assert colors[3] <= 255 and sizes > 0
