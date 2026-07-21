"""OpenAPI catalogue coverage and metadata regression tests."""

from __future__ import annotations

import ast
from pathlib import Path

from sanic_ext.extensions.openapi.builders import OperationStore, SpecificationBuilder

from application import app
from contexts.shared.interface.api_documentation import CATALOG


ROOT = Path(__file__).parents[1]


def _controller_route_methods(path: Path) -> tuple[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    controller = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Controller")
    )
    setup = next(
        node
        for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "setup"
    )
    methods: set[str] = set()
    for call in (node for node in ast.walk(setup) if isinstance(node, ast.Call)):
        if not call.args:
            continue
        first = call.args[0]
        if (
            isinstance(first, ast.Attribute)
            and isinstance(first.value, ast.Name)
            and first.value.id == "self"
        ):
            methods.add(first.attr)
    return controller.name, methods


def test_every_http_controller_route_is_in_openapi_catalogue():
    interface_files = (ROOT / "contexts").glob("*/interface/*controller.py")
    covered_classes = set()
    for path in interface_files:
        if path.name in {"base_controller.py", "health_controller.py"}:
            continue
        class_name, route_methods = _controller_route_methods(path)
        if not route_methods:
            continue
        # WebSockets are not representable in an OpenAPI HTTP operation.
        route_methods.discard("stream")
        assert set(CATALOG[class_name]) == route_methods
        covered_classes.add(class_name)
    assert covered_classes == set(CATALOG)


def test_registered_http_routes_have_complete_openapi_metadata():
    store = OperationStore()
    missing = []
    for route in app.router.routes:
        if route.path.startswith("docs") or route.path.endswith("ws/alerts"):
            continue
        handler = route.handler
        operation = store.get(handler)
        if operation is None and getattr(handler, "__func__", None) is not None:
            operation = store.get(handler.__func__)
        if operation is None:
            missing.append((route.path, "operation"))
            continue
        if operation._exclude:
            continue
        if not getattr(operation, "summary", None):
            missing.append((route.path, "summary"))
        if not getattr(operation, "description", None):
            missing.append((route.path, "description"))
        if not operation.responses:
            missing.append((route.path, "responses"))
    assert missing == []


def test_bearer_security_scheme_is_registered():
    components = SpecificationBuilder().build(app).serialize()["components"]
    assert components["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_swagger_is_the_default_interactive_docs_ui():
    assert app.config.OAS_UI_DEFAULT == "swagger"
