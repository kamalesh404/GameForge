"""Tests for collision shapes, rigid bodies, quadtree, joints, and solver."""

import pytest

from src.math.vector import Vector2
from src.physics.collider import (
    AABB,
    AABBCollider,
    CircleCollider,
    PolygonCollider,
    aabb_vs_aabb,
    aabb_vs_circle,
    circle_vs_circle,
    detect,
    sat_polygon,
)
from src.physics.joints import DistanceJoint, PrismaticJoint, RevoluteJoint, solve_joints
from src.physics.rigidbody import RigidBody
from src.physics.world import PhysicsWorld, Quadtree


class TestColliders:
    def test_aabb_overlap_detection(self) -> None:
        a = AABBCollider(Vector2(0, 0), Vector2(10, 10))
        far = AABBCollider(Vector2(25, 0), Vector2(10, 10))   # gap between x=10 and x=15
        touching = AABBCollider(Vector2(8, 0), Vector2(5, 5))  # overlaps by 7 on x
        assert not aabb_vs_aabb(a, far)
        normal, depth = aabb_vs_aabb(a, touching)
        # normal points from a toward the overlapping box on its right
        assert normal.x == pytest.approx(1.0) and depth == pytest.approx(7.0)

    def test_circle_collision(self) -> None:
        a = CircleCollider(Vector2(0, 0), radius=5)
        b = CircleCollider(Vector2(6, 0), radius=4)
        normal, depth = circle_vs_circle(a, b)
        assert normal.x > 0.99 and depth == pytest.approx(3.0)

    def test_circle_center_inside_box(self) -> None:
        box = AABBCollider(Vector2(0, 0), Vector2(2, 2))
        ball = CircleCollider(Vector2(1.9, 0), radius=1)
        contact = aabb_vs_circle(box, ball)
        assert contact is not None
        normal, depth = contact
        assert depth == pytest.approx(1.0)  # closest surface point coincides with center

    def test_polygon_sat_hit_and_miss(self) -> None:
        square_a = PolygonCollider(Vector2(0, 0), [Vector2(-4, -4), Vector2(4, -4),
                                                   Vector2(4, 4), Vector2(-4, 4)])
        square_b = PolygonCollider(Vector2(3, 0), [Vector2(-2, -2), Vector2(2, -2),
                                                   Vector2(2, 2), Vector2(-2, 2)])
        far = PolygonCollider(Vector2(100, 100), [Vector2(-2, -2), Vector2(2, -2),
                                                  Vector2(2, 2), Vector2(-2, 2)])
        hit = sat_polygon(square_a, square_b)
        assert hit is not None and hit[1] > 0
        assert sat_polygon(square_a, far) is None

    def test_detect_dispatch_table(self) -> None:
        box = AABBCollider(Vector2(0, 0), Vector2(1, 1))
        ball = CircleCollider(Vector2(1.5, 0), radius=0.75)
        assert detect(box, ball) is not None
        assert detect(box, box) is not None


class TestRigidBody:
    def test_gravity_integration(self) -> None:
        body = RigidBody(position=Vector2(0, 100))
        body.integrate(1 / 60)
        assert body.position.y < 100 and body.velocity.y < 0

    def test_impulse_changes_velocity_by_mass(self) -> None:
        heavy = RigidBody(mass=4.0)
        light = RigidBody(mass=1.0)
        heavy.apply_impulse(Vector2(40, 0))
        light.apply_impulse(Vector2(40, 0))
        assert heavy.velocity.x == pytest.approx(10.0)
        assert light.velocity.x == pytest.approx(40.0)

    def test_static_body_never_moves(self) -> None:
        body = RigidBody(body_type="static")
        body.integrate(0.1)
        body.apply_impulse(Vector2(100, 0))
        assert body.inverse_mass == 0.0
        assert body.velocity.length() == 0.0

    def test_damping_slows_motion(self) -> None:
        body = RigidBody()
        body.linear_damping = 5.0
        body.velocity = Vector2(100, 0)
        body.integrate(0.5)
        assert body.speed() < 50


class TestQuadtree:
    def test_insert_query_roundtrip(self) -> None:
        tree = Quadtree(AABB(Vector2(0, 0), Vector2(100, 100)))
        items = {f"item{i}": AABB(Vector2(i * 10 + 1, 1), Vector2(i * 10 + 5, 5))
                 for i in range(12)}
        for name, box in items.items():
            tree.insert(name, box)
        hits = tree.query(AABB(Vector2(0, 0), Vector2(25, 20)))
        assert "item0" in hits and "item2" in hits
        assert "item11" not in hits

    def test_clear_resets(self) -> None:
        tree = Quadtree(AABB(Vector2(0, 0), Vector2(50, 50)))
        tree.insert("x", AABB(Vector2(1, 1), Vector2(2, 2)))
        tree.clear()
        assert tree.query(AABB(Vector2(0, 0), Vector2(50, 50))) == set()


class TestPhysicsWorld:
    def _make_pair(self, separation: float):
        world = PhysicsWorld(gravity=Vector2(0, 0))
        body_a = RigidBody(position=Vector2(0, 0))
        body_b = RigidBody(position=Vector2(separation, 0))
        shape_a = AABBCollider(body_a.position, Vector2(10, 10))
        shape_b = AABBCollider(body_b.position, Vector2(10, 10))
        world.add_body(body_a, shape_a)
        world.add_body(body_b, shape_b)
        return world, body_a, body_b

    def test_overlapping_bodies_separate(self) -> None:
        world, a, b = self._make_pair(separation=12.0)
        resolved = world.step(1 / 60)
        assert resolved >= 1
        gap = abs(b.position.x - a.position.x)
        assert gap > 18.0  # positional correction pushes toward non-overlap

    def test_sensor_bodies_skip_resolution(self) -> None:
        world = PhysicsWorld(gravity=Vector2(0, 0))
        a = RigidBody(position=Vector2(0, 0))
        b = RigidBody(position=Vector2(5, 0))
        sa = AABBCollider(a.position, Vector2(10, 10))
        sb = AABBCollider(b.position, Vector2(10, 10))
        world.add_body(a, sa)
        world.add_body(b, sb, sensor_only=True)
        world.step(1 / 60)
        assert abs(b.position.x - 5.0) < 1e-6

    def test_listener_receives_contacts(self) -> None:
        world, a, b = self._make_pair(separation=10.0)

        class Recorder:
            def __init__(self) -> None:
                self.contacts: list = []

            def on_contact(self, first, second, normal, depth):
                self.contacts.append((first, second))

        rec = Recorder()
        world.contact_listeners.append(rec)
        world.step(1 / 60)
        assert len(rec.contacts) >= 1


class TestJoints:
    def test_distance_joint_pulls_to_rest_length(self) -> None:
        a = RigidBody(position=Vector2(0, 0))
        b = RigidBody(position=Vector2(30, 0))
        joint = DistanceJoint(a, b, length=80.0, stiffness=0.5, damping=0.0)
        solve_joints([joint], iterations=20)
        assert abs(joint.current_distance() - 80.0) < 5.0

    def test_revolute_joint_converges_on_anchor(self) -> None:
        a = RigidBody(position=Vector2(-50, 0))
        b = RigidBody(position=Vector2(50, 0))
        anchor = Vector2(10, 5)
        joint = RevoluteJoint(a, b, anchor)
        solve_joints([joint], iterations=30)
        assert a.position.distance_to(anchor) < 1.0
        assert b.position.distance_to(anchor) < 1.0

    def test_prismatic_joint_clamps_axis_limits(self) -> None:
        a = RigidBody(position=Vector2(0, 0))
        b = RigidBody(position=Vector2(500, 0))
        joint = PrismaticJoint(a, b, axis_degrees=0.0, min_limit=-100, max_limit=100)
        solve_joints([joint], iterations=40)
        assert abs(joint.projection()) <= 105
