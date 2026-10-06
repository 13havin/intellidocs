from datetime import timedelta

import jwt
import pytest

from app.core.config import ALGORITHM
from app.core.tokens import create_access_token


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_profile_requires_token(test_client):
    assert_unauthorized(test_client.get("/api/v1/users/me"))


def test_profile_rejects_malformed_token(test_client):
    response = test_client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"})
    assert_unauthorized(response)


def test_profile_rejects_expired_token(test_client, registered_user):
    token = create_access_token({"sub": registered_user["email"]}, expires_delta=timedelta(minutes=-1))
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


def test_profile_rejects_wrong_signature(test_client, registered_user):
    token = jwt.encode({"sub": registered_user["email"]}, "different-test-signing-key-12345678901234567890", algorithm=ALGORITHM)
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


@pytest.mark.parametrize("claims", [{}, {"sub": ""}, {"sub": 123}])
def test_profile_rejects_invalid_subject(test_client, claims):
    token = create_access_token(claims)
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)


def test_profile_rejects_unknown_user(test_client, user_payload_valid):
    token = create_access_token({"sub": user_payload_valid["email"]})
    response = test_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert_unauthorized(response)
