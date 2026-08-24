"""Tests for the infra compiler, validator, planner and state backends."""

from __future__ import annotations

import pytest

from src.infra.compiler import CompileError, InfraCompiler, parse_stack
from src.infra.diff import Action, compute_plan
from src.infra.state import LocalStateBackend, S3StateBackend
from src.infra.validator import (
    CircularDependencyError,
    DependencyGraph,
    validate_specs,
)
from src.providers.base import ResourceKind, ResourceSpec


def test_parse_stack_extracts_definition(stack_document: dict) -> None:
    definition = parse_stack(stack_document)

    assert definition.name == "shop"
    assert definition.provider == "fake"
    assert definition.region == "us-east-1"
    assert definition.template == "web-app"
    assert definition.uses_template()


def test_parse_stack_requires_name_and_provider() -> None:
    with pytest.raises(CompileError, match="missing required keys"):
        parse_stack({"region": "us-east-1"})


def test_compile_applies_region_and_stack_tags(
    stack_document: dict,
    fake_provider,
) -> None:
    stack_document["region"] = "eu-west-1"
    definition = parse_stack(stack_document)
    specs = InfraCompiler(fake_provider).compile(definition)

    assert len(specs) == 5
    assert all(spec.region == "eu-west-1" for spec in specs)
    assert all(spec.tags["stack"] == "shop" for spec in specs)
    assert all(spec.tags["template"] == "web-app" for spec in specs)


def test_dependency_graph_orders_and_detects_cycles() -> None:
    base = ResourceSpec(kind=ResourceKind.NETWORK, name="vpc")
    app = ResourceSpec(
        kind=ResourceKind.COMPUTE,
        name="api",
        config={"depends_on": ["vpc", "cache"]},
    )
    cache = ResourceSpec(kind=ResourceKind.DATABASE, name="cache")

    graph = DependencyGraph.from_specs([app, base, cache])
    order = graph.topological_order()
    assert set(order) == {"vpc", "api", "cache"}
    assert order.index("vpc") < order.index("api")
    assert graph.dependencies_of("api") == {"vpc", "cache"}

    cyclic = DependencyGraph.from_specs(
        [
            ResourceSpec(kind=ResourceKind.COMPUTE, name="a", config={"depends_on": ["b"]}),
            ResourceSpec(kind=ResourceKind.COMPUTE, name="b", config={"depends_on": ["a"]}),
        ],
    )
    with pytest.raises(CircularDependencyError):
        cyclic.topological_order()


def test_validate_specs_reports_duplicates() -> None:
    duplicated = [
        ResourceSpec(kind=ResourceKind.STORAGE, name="assets"),
        ResourceSpec(kind=ResourceKind.CDN, name="assets"),
    ]
    errors = validate_specs(duplicated)
    assert any("duplicate resource name" in error for error in errors)


def test_plan_lifecycle_create_update_delete(
    web_app_specs,
    fake_provider,
    state_backend: LocalStateBackend,
) -> None:
    compiler = InfraCompiler(fake_provider)
    provisioned = compiler.apply(web_app_specs)
    state_backend.save("shop", provisioned)

    entries = state_backend.load("shop")
    desired = [spec for spec in web_app_specs if spec.name != "shop-cdn"]
    web = next(spec for spec in desired if spec.name == "shop-web")
    web.replicas = 5

    plan = compute_plan("shop", desired, entries)
    assert plan.create_count == 0
    assert plan.update_count == 1
    assert plan.delete_count == 1
    assert plan.noop_count == 3
    assert not plan.is_empty
    assert "to create" in plan.summary()

    actions = {change.name: change.action for change in plan.changes}
    assert actions["shop-web"] is Action.UPDATE
    assert actions["shop-cdn"] is Action.DELETE


def test_plan_on_empty_state_is_all_creates(web_app_specs) -> None:
    plan = compute_plan("shop", web_app_specs, [])
    assert plan.create_count == 5
    assert plan.delete_count == 0
    empty_plan = compute_plan("shop", [], [])
    assert empty_plan.is_empty and len(empty_plan.changes) == 0


def test_local_state_roundtrip(state_backend: LocalStateBackend, fake_provider) -> None:
    spec = ResourceSpec(kind=ResourceKind.STORAGE, name="media-bucket")
    resource = fake_provider.provision(spec)
    state_backend.save("demo", [resource])

    entries = state_backend.load("demo")
    assert len(entries) == 1
    assert entries[0]["provider_id"] == resource.provider_id
    assert entries[0]["kind"] == ResourceKind.STORAGE.value
    assert state_backend.list_stacks() == ["demo"]
    assert state_backend.delete("demo") is True
    assert state_backend.load("demo") == []


def test_s3_state_backend_with_memory_fallback() -> None:
    from src.providers.base import ProvisionedResource, ResourceStatus

    backend = S3StateBackend(bucket="clouddeploy-state")
    spec = ResourceSpec(kind=ResourceKind.QUEUE, name="events")
    resource = ProvisionedResource(spec=spec, provider_id="q-1", status=ResourceStatus.ACTIVE)

    backend.save("shop", [resource])
    loaded = backend.load("shop")
    assert loaded[0]["name"] == "events"
    assert backend.delete("shop") is True
    assert backend.load("shop") == []
    assert backend.delete("shop") is False


def test_s3_backend_uses_injected_client() -> None:
    import io

    from src.providers.base import ProvisionedResource, ResourceStatus

    calls: list[tuple[str, str]] = []

    class FakeS3Client:
        def __init__(self) -> None:
            self.bodies: dict[str, bytes] = {}

        def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
            calls.append(("put", Key))
            self.bodies[Key] = Body

        def get_object(self, Bucket: str, Key: str) -> dict:
            calls.append(("get", Key))
            return {"Body": io.BytesIO(self.bodies[Key])}

        def head_object(self, Bucket: str, Key: str) -> bool:
            return Key in self.bodies

        def delete_object(self, Bucket: str, Key: str) -> None:
            calls.append(("delete", Key))
            del self.bodies[Key]

    client = FakeS3Client()
    backend = S3StateBackend(bucket="clouddeploy-state", client=client)

    spec = ResourceSpec(kind=ResourceKind.COMPUTE, name="svc")
    resource = ProvisionedResource(spec=spec, provider_id="i-1", status=ResourceStatus.ACTIVE)
    backend.save("shop", [resource])

    assert ("put", "stacks/shop.json") in calls
    assert backend.load("shop")[0]["name"] == "svc"
    backend.delete("shop")
    assert ("delete", "stacks/shop.json") in calls
