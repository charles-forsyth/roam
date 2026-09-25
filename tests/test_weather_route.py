from roam.core import RouteRequester


def test_route_weather_uses_existing_forecast_method():
    """`roam ... --weather` called a non-existent get_weather_forecast()."""
    assert not hasattr(RouteRequester, "get_weather_forecast")
    assert hasattr(RouteRequester, "get_hourly_forecast")
    import inspect

    from roam import cli

    src = inspect.getsource(cli)
    assert "get_weather_forecast" not in src
    assert "requester.get_hourly_forecast(" in src
