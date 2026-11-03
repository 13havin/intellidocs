from datetime import timedelta

import jwt
import pytest

from app.core.config import ALGORITHM
from app.core.tokens import create_access_token
from app.core.tokens import verify_token


def test_profile_accepts_login_token_with_user_id(test_client, user_payload_valid):
    payload = {**user_payload_valid, "password": "Securepassword123"}
    registered = test_client.post("/auth/register", json=payload)
    assert registered.status_code == 201
    login = test_client.post("/auth/login", data={
        "username": payload["email"], "password": payload["password"],
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert verify_token(token).id == registered.json()["id"]
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == registered.json()


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_profile_requires_token(test_client):
    assert_unauthorized(test_client.get("/api/v1/users/me"))


def test_profile_rejects_malformed_token(test_client):
    response = test_client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"})
    assert_unauthorized(response)


def test_profile_rejects_expired_token(test_client, registered_user):
    token = create_access_token({"sub": str(registered_user["id"])}, expires_delta=timedelta(minutes=-1))
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


def test_profile_rejects_wrong_signature(test_client, registered_user):
    token = jwt.encode({"sub": str(registered_user["id"])}, "different-test-signing-key-12345678901234567890", algorithm=ALGORITHM)
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


@pytest.mark.parametrize("claims", [{}, {"sub": ""}, {"sub": 123}, {"sub": "old@example.com"}])
def test_profile_rejects_invalid_subject(test_client, claims):
    token = create_access_token(claims)
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


def test_profile_rejects_unknown_user(test_client):
    token = create_access_token({"sub": "-1"})
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)
