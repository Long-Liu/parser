"""Explicit Sanic controller registration."""

from collections.abc import Iterable

from contexts.shared.interface.api_documentation import apply_controller_docs
from contexts.shared.interface.base_controller import BaseController


def register_controllers(app, controllers: Iterable[BaseController]) -> None:
    for controller in controllers:
        apply_controller_docs(controller)
        controller.setup()
        app.blueprint(controller.bp)
