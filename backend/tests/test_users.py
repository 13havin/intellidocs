def test_user_creation_and_retrieval(test_client, user_payload_valid, user_endpoint):
    response = test_client.post(f"{user_endpoint}/", json=user_payload_valid)
    assert response.status_code == 201
    created_user = response.json()
    assert created_user["name"] == user_payload_valid["name"]
    assert created_user["email"] == user_payload_valid["email"]

    response = test_client.get(f"{user_endpoint}/{created_user['id']}")
    assert response.status_code == 200
    assert response.json() == created_user


def test_user_creation_same_email(test_client, user_payload_valid, user_endpoint):
    response = test_client.post(f"{user_endpoint}/", json=user_payload_valid)
    assert response.status_code == 201
    response = test_client.post(f"{user_endpoint}/", json=user_payload_valid)
    assert response.status_code == 409


def test_user_creation_invalid_email(test_client, user_payload_invalid, user_endpoint):
    response = test_client.post(f"{user_endpoint}/", json=user_payload_invalid)
    assert response.status_code == 422


def test_get_nonexistent_user(test_client, user_endpoint):
    response = test_client.get(f"{user_endpoint}/-1")
    assert response.status_code == 404
