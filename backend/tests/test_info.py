def test_info_check(test_client, expected_info_response, info_endpoint):
    response = test_client.get(info_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_info_response
