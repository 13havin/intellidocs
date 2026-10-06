import pytest

from app.core.security import verify_password
from app.models.user import User


def test_register_login_and_get_profile(test_client, user_payload_valid):
    # Register.
    response = test_client.post(
        "/auth/register",
        json=user_payload_valid,
    )
    assert response.status_code == 201

    registered_user = response.json()
    assert set(registered_user) == {"id", "name", "email"}

    # Login uses form data, not JSON.
    response = test_client.post(
        "/auth/login",
        data={
            "username": user_payload_valid["email"],
            "password": user_payload_valid["password"],
        },
    )
    assert response.status_code == 200

    token = response.json()
    assert token["access_token"]
    assert token["token_type"].lower() == "bearer"

    # Access the protected profile.
    response = test_client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token['access_token']}",
        },
    )
    assert response.status_code == 200
    assert response.json() == registered_user
    assert response.json()["email"] == user_payload_valid["email"]


def test_registration_stores_password_hash(test_client, db_session, user_payload_valid):
    response = test_client.post("/auth/register", json=user_payload_valid)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "name", "email"}
    stored_user = db_session.get(User, response.json()["id"])
    assert stored_user.password != user_payload_valid["password"]
    assert verify_password(user_payload_valid["password"], stored_user.password)


def test_registration_rejects_duplicate_email(test_client, registered_user, user_payload_valid):
    response = test_client.post("/auth/register", json=user_payload_valid)
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_registration_rejects_invalid_email(test_client, user_payload_invalid):
    response = test_client.post("/auth/register", json=user_payload_invalid)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "email"] for error in response.json()["detail"])


@pytest.mark.parametrize("missing_field", ["name", "email", "password"])
def test_registration_requires_fields(test_client, user_payload_valid, missing_field):
    payload = dict(user_payload_valid)
    del payload[missing_field]
    response = test_client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", missing_field] for error in response.json()["detail"])


def test_login_rejects_wrong_password(test_client, registered_user, user_payload_valid):
    response = test_client.post("/auth/login", data={
        "username": user_payload_valid["email"], "password": "wrong-password",
    })
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_rejects_unknown_email(test_client, user_payload_valid):
    response = test_client.post("/auth/login", data={
        "username": user_payload_valid["email"], "password": user_payload_valid["password"],
    })
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize("missing_field", ["username", "password"])
def test_login_requires_form_fields(test_client, user_payload_valid, missing_field):
    data = {"username": user_payload_valid["email"], "password": user_payload_valid["password"]}
    del data[missing_field]
    response = test_client.post("/auth/login", data=data)
    assert response.status_code == 422
