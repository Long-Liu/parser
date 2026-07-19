def test_application_controllers_can_be_assembled():
    import application

    assert application.app.name == "excel_parser"
    assert len(application.app.router.routes) >= 70


def test_auth_and_analytics_controllers_are_registered():
    import application

    route_names = {route.name for route in application.app.router.routes}
    assert any(".auth." in name for name in route_names)
    assert any("analytics" in name for name in route_names)


def test_dependency_container_is_application_scoped():
    from contexts.container import build_container
    from contexts.shared.infrastructure.config import Settings

    first = build_container(Settings())
    second = build_container(Settings())

    assert first is not second
    assert first.user_service is not second.user_service


def test_component_overrides_are_applied_to_all_transactional_services():
    from contexts.container import ComponentOverrides, build_container
    from contexts.shared.application.transaction import NoopTransactionManager
    from contexts.shared.infrastructure.config import Settings

    transactions = NoopTransactionManager()
    components = build_container(
        Settings(), ComponentOverrides(transaction_manager=transactions),
    )

    assert components.auth_service.transaction_manager is transactions
    assert components.upload_service.transaction_manager is transactions
