"""Explicit Sanic controller registration."""

from collections.abc import Iterable

from contexts.shared.interface.base_controller import BaseController


def register_controllers(app, controllers: Iterable[BaseController]) -> None:
    for controller in controllers:
        controller.setup()
        app.blueprint(controller.bp)
