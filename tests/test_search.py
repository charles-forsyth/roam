from roam.core import RouteRequester

def test_search_along_route_mock(mocker):
    # Mock requests.Session.post
    mock_post = mocker.patch("requests.Session.post")
    
    # Setup mock response for search
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "places": [
            {
                "displayName": {"text": "Joe's Coffee"},
                "formattedAddress": "123 Route 66",
                "location": {"latitude": 10, "longitude": 20}
            }
        ]
    }
    mock_post.return_value = mock_response

    requester = RouteRequester(api_key="fake_key")
    results = requester.search_along_route("coffee", "dummy_polyline")

    assert len(results) == 1
    assert results[0]["displayName"]["text"] == "Joe's Coffee"
    
    # Verify payload structure
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["textQuery"] == "coffee"
    assert kwargs["json"]["searchAlongRouteParameters"]["polyline"]["encodedPolyline"] == "dummy_polyline"
