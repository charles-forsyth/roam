from roam.core import RouteRequester


def test_compute_route_mock(mocker):
    # Mock requests.Session.post
    mock_post = mocker.patch("requests.Session.post")

    # Setup mock response
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "routes": [
            {
                "distanceMeters": 16093,  # ~10 miles
                "duration": "1200s",
                "polyline": {"encodedPolyline": "dummy_polyline"},
            }
        ]
    }
    mock_post.return_value = mock_response

    requester = RouteRequester(api_key="fake_key")
    result = requester.compute_route("Origin", "Dest", mode="drive")

    assert result["routes"][0]["distanceMeters"] == 16093
    mock_post.assert_called_once()


def test_get_daily_forecast_mock(mocker):
    mock_get = mocker.patch("requests.get")
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"forecastDays": []}
    mock_get.return_value = mock_response

    requester = RouteRequester(api_key="fake_key")
    result = requester.get_daily_forecast(40.7128, -74.0060)

    assert "forecastDays" in result
    mock_get.assert_called_once()
