from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.tokens import create_access_token
from app.models.user import User
from app.models.workspace_members import WorkspaceMember
from app.models.workspaces import Workspace
from app.services import workspace_service


ENDPOINT = "/api/v1/workspaces/"


@pytest.fixture
def workspace_users(db_session):
    users = [
        User(name=name, email=f"{uuid4().hex}@example.com", password="unused")
        for name in ("Creator", "Other user")
    ]
    db_session.add_all(users)
    db_session.commit()
    return users


def auth_headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_create_persists_workspace_and_authenticated_owner(
    test_client, db_session, workspace_users
):
    creator, other = workspace_users
    response = test_client.post(
        ENDPOINT,
        json={"name": "Project documents", "creator_id": other.id, "role": "viewer"},
        headers=auth_headers(creator),
    )
    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"id", "name", "created_at", "updated_at"}
    assert payload["name"] == "Project documents"
    for field in ("created_at", "updated_at"):
        assert isinstance(payload[field], str)
        datetime.fromisoformat(payload[field])

    # Discard the current transaction and identity map: flushed-only inserts
    # would disappear here, while the service's committed savepoint survives.
    creator_id = creator.id
    db_session.rollback()
    db_session.expunge_all()
    workspace = db_session.get(Workspace, payload["id"])
    assert workspace is not None
    assert workspace.name == payload["name"]
    members = db_session.scalars(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id)
    ).all()
    assert len(members) == 1
    assert (members[0].user_id, members[0].role) == (creator_id, "owner")


@pytest.mark.parametrize("method,path", [
    ("POST", ENDPOINT), ("GET", ENDPOINT), ("GET", f"{ENDPOINT}1"),
])
@pytest.mark.parametrize("credential", ["missing", "invalid", "expired", "unknown_user"])
def test_workspace_endpoints_require_authentication(
    test_client, db_session, workspace_users, method, path, credential
):
    headers = {}
    if credential == "invalid":
        headers = {"Authorization": "Bearer not-a-valid-token"}
    elif credential == "expired":
        token = create_access_token(
            {"sub": str(workspace_users[0].id)}, expires_delta=timedelta(minutes=-1)
        )
        headers = {"Authorization": f"Bearer {token}"}
    elif credential == "unknown_user":
        token = create_access_token({"sub": "-1"})
        headers = {"Authorization": f"Bearer {token}"}

    kwargs = {"json": {"name": "Unauthorized"}} if method == "POST" else {}
    response = test_client.request(method, path, headers=headers, **kwargs)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.scalars(select(Workspace)).all() == []
    assert db_session.scalars(select(WorkspaceMember)).all() == []


def test_create_requires_name(test_client, db_session, workspace_users):
    response = test_client.post(ENDPOINT, json={}, headers=auth_headers(workspace_users[0]))
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "name"] for error in response.json()["detail"])
    assert db_session.scalars(select(Workspace)).all() == []


@pytest.mark.parametrize("name", ["", "   ", "\t\n", None, 123])
def test_create_rejects_invalid_name(test_client, db_session, workspace_users, name):
    response = test_client.post(
        ENDPOINT, json={"name": name}, headers=auth_headers(workspace_users[0])
    )
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "name"] for error in response.json()["detail"])
    assert db_session.scalars(select(Workspace)).all() == []
    assert db_session.scalars(select(WorkspaceMember)).all() == []


def test_create_requires_json_body_not_query_name(test_client, db_session, workspace_users):
    response = test_client.post(
        ENDPOINT, params={"name": "Query only"}, headers=auth_headers(workspace_users[0])
    )
    assert response.status_code == 422
    assert any(error["loc"] == ["body"] for error in response.json()["detail"])
    assert db_session.scalars(select(Workspace)).all() == []
    assert db_session.scalars(select(WorkspaceMember)).all() == []


def test_list_returns_only_memberships_without_duplicates(test_client, db_session, workspace_users):
    user, other = workspace_users
    owned = workspace_service.create_workspace(db_session, "Owned", user.id)
    shared = workspace_service.create_workspace(db_session, "Shared", other.id)
    workspace_service.create_workspace(db_session, "Private", other.id)
    db_session.add_all([
        WorkspaceMember(workspace_id=owned.id, user_id=other.id, role="editor"),
        WorkspaceMember(workspace_id=shared.id, user_id=user.id, role="viewer"),
    ])
    db_session.commit()

    response = test_client.get(ENDPOINT, headers=auth_headers(user))
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert {row["id"] for row in payload} == {owned.id, shared.id}


def test_list_without_memberships_returns_404(test_client, db_session, workspace_users):
    user, other = workspace_users
    workspace_service.create_workspace(db_session, "Someone else's", other.id)
    response = test_client.get(ENDPOINT, headers=auth_headers(user))
    assert response.status_code == 404
    assert response.json() == {"detail": "No workspaces found"}


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
def test_get_workspace_allows_members(test_client, db_session, workspace_users, role):
    user, other = workspace_users
    workspace = workspace_service.create_workspace(db_session, "Accessible", other.id)
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    db_session.commit()

    response = test_client.get(f"{ENDPOINT}{workspace.id}", headers=auth_headers(user))
    assert response.status_code == 200
    assert response.json()["id"] == workspace.id
    assert response.json()["name"] == "Accessible"


@pytest.mark.parametrize("existing", [True, False])
def test_get_inaccessible_or_missing_workspace_returns_404(
    test_client, db_session, workspace_users, existing
):
    user, other = workspace_users
    workspace_id = -1
    if existing:
        workspace_id = workspace_service.create_workspace(db_session, "Private", other.id).id
    response = test_client.get(f"{ENDPOINT}{workspace_id}", headers=auth_headers(user))
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


def test_create_rolls_back_workspace_when_membership_fails(db_session, workspace_users):
    with pytest.raises(IntegrityError):
        workspace_service.create_workspace(db_session, "Must roll back", creator_id=-1)

    assert db_session.scalars(select(Workspace)).all() == []
    assert db_session.scalars(select(WorkspaceMember)).all() == []
    # The service must leave the session usable after a failed transaction.
    workspace = workspace_service.create_workspace(db_session, "Recovery", workspace_users[0].id)
    assert db_session.get(Workspace, workspace.id).name == "Recovery"
