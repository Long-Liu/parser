"""Spring-style @rest_controller auto-registration for Sanic blueprints.

Usage — in a controller file::

    from contexts.shared.interface.rest_controller import rest_controller

    @rest_controller("/api")
    class UsersController:
        def __init__(self, user_svc: UserApplicationService):
            self.svc = user_svc
            self.bp = Blueprint("users", url_prefix="/api")
            self._register()
        ...

Usage — in application.py::

    import contexts.shared.interface.rest_controller as rc
    rc.register_all(app, container)
"""

from __future__ import annotations

_controllers: list[type] = []


def rest_controller(url_prefix: str):
    """Class decorator — marks the class for auto-discovery and records its url_prefix."""

    def decorator(cls):
        cls.__rest_prefix__ = url_prefix
        _controllers.append(cls)
        return cls

    return decorator


def register_all(app, container) -> None:
    """Instantiate every @rest_controller class via the DI container, then mount its .bp.

    Call once in application.py after container.wire() has completed.
    """
    for cls in _controllers:
        instance = container.resolve(cls)
        instance.setup()
        app.blueprint(instance.bp)
