def test_health_check(test_client, expected_health_response, health_endpoint):
    response = test_client.get(health_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_health_response
