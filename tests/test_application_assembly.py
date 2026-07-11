def test_application_controllers_can_be_assembled():
    import application

    assert application.app.name == "excel_parser"
    assert len(application.app.router.routes) >= 70


def test_auth_and_analytics_controllers_are_registered():
    import application

    route_names = {route.name for route in application.app.router.routes}
    assert any("auth_ddd" in name for name in route_names)
    assert any("analytics" in name for name in route_names)
