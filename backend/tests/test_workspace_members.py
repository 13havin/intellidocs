from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tokens import create_access_token
from app.models.user import User
from app.models.workspace_members import WorkspaceMember
from app.schemas.workspace_members import RoleEnum
from app.services import workspace_members_service, workspace_service


@pytest.fixture
def member_context(db_session):
    users = {
        name: User(name=name, email=f"{uuid4().hex}@example.com", password="unused")
        for name in ("owner", "editor", "viewer", "outsider", "target")
    }
    db_session.add_all(users.values())
    db_session.commit()
    workspace = workspace_service.create_workspace(db_session, "Members test", users["owner"].id)
    for role in ("editor", "viewer"):
        db_session.add(WorkspaceMember(
            workspace_id=workspace.id, user_id=users[role].id, role=role,
        ))
    db_session.commit()
    return workspace, users


@pytest.fixture
def member_client(test_client):
    # Assert HTTP behavior, including response-serialization failures as 500s.
    with TestClient(test_client.app, raise_server_exceptions=False) as client:
        yield client


def headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def endpoint(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/members"


def membership_ids(db):
    return set(db.scalars(select(WorkspaceMember.id)).all())


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
def test_owner_can_add_member(member_client, db_session, member_context, role):
    workspace, users = member_context
    target_id = users["target"].id
    workspace_id = workspace.id
    email = users["target"].email
    response = member_client.post(
        endpoint(workspace_id), headers=headers(users["owner"]),
        json={"email": email, "role": role},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert set(data) == {"email", "role", "joined_at"}
    assert data["email"] == email
    assert data["role"] == role
    datetime.fromisoformat(data["joined_at"])
    db_session.rollback()
    db_session.expunge_all()
    member = workspace_members_service.get_workspace_member(db_session, workspace_id, target_id)
    assert member is not None
    assert member.role == role


@pytest.mark.parametrize("actor,status", [("outsider", 404), ("editor", 403), ("viewer", 403)])
@pytest.mark.parametrize("target_exists", [True, False])
def test_add_checks_requester_before_target_lookup(
    member_client, db_session, member_context, actor, status, target_exists
):
    workspace, users = member_context
    before = membership_ids(db_session)
    email = users["target"].email if target_exists else "missing@example.com"
    response = member_client.post(
        endpoint(workspace.id), headers=headers(users[actor]),
        json={"email": email, "role": "viewer"},
    )
    assert response.status_code == status
    detail = "Workspace not found" if status == 404 else "You do not have permission to add members to this workspace"
    assert response.json() == {"detail": detail}
    assert membership_ids(db_session) == before


def test_add_to_missing_workspace_returns_404(member_client, db_session, member_context):
    _, users = member_context
    before = membership_ids(db_session)
    response = member_client.post(
        endpoint(-1), headers=headers(users["owner"]),
        json={"email": users["target"].email, "role": "viewer"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}
    assert membership_ids(db_session) == before


def test_add_unknown_user_returns_404(member_client, db_session, member_context):
    workspace, users = member_context
    before = membership_ids(db_session)
    response = member_client.post(
        endpoint(workspace.id), headers=headers(users["owner"]),
        json={"email": "missing@example.com", "role": "viewer"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "missing@example.com is not found"}
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("target", ["owner", "editor"])
def test_add_existing_member_returns_409(member_client, db_session, member_context, target):
    workspace, users = member_context
    before = membership_ids(db_session)
    response = member_client.post(
        endpoint(workspace.id), headers=headers(users["owner"]),
        json={"email": users[target].email, "role": "viewer"},
    )
    assert response.status_code == 409
    assert membership_ids(db_session) == before
    member = workspace_members_service.get_workspace_member(db_session, workspace.id, users[target].id)
    assert member.role == target


@pytest.mark.parametrize("payload,field", [
    ({"role": "viewer"}, "email"),
    ({"email": "valid@example.com"}, "role"),
    ({"email": "invalid", "role": "viewer"}, "email"),
    ({"email": "valid@example.com", "role": "admin"}, "role"),
])
def test_add_validates_payload(member_client, db_session, member_context, payload, field):
    workspace, users = member_context
    before = membership_ids(db_session)
    response = member_client.post(endpoint(workspace.id), headers=headers(users["owner"]), json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("invalid_token", [False, True])
def test_member_endpoints_require_authentication(
    member_client, db_session, member_context, method, invalid_token
):
    workspace, users = member_context
    before = membership_ids(db_session)
    auth = {"Authorization": "Bearer invalid"} if invalid_token else {}
    kwargs = {"json": {"email": users["target"].email, "role": "viewer"}} if method == "POST" else {}
    response = member_client.request(method, endpoint(workspace.id), headers=auth, **kwargs)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("actor", ["owner", "editor", "viewer"])
def test_members_can_list_only_requested_workspace(member_client, db_session, member_context, actor):
    workspace, users = member_context
    workspace_service.create_workspace(db_session, "Other workspace", users["outsider"].id)
    response = member_client.get(endpoint(workspace.id), headers=headers(users[actor]))
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 3
    assert {(row["email"], row["role"]) for row in data} == {
        (users[role].email, role) for role in ("owner", "editor", "viewer")
    }
    for row in data:
        assert set(row) == {"email", "role", "joined_at"}
        datetime.fromisoformat(row["joined_at"])


@pytest.mark.parametrize("exists", [True, False])
def test_list_hides_inaccessible_or_missing_workspace(member_client, member_context, exists):
    workspace, users = member_context
    response = member_client.get(
        endpoint(workspace.id if exists else -1), headers=headers(users["outsider"]),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


def test_get_member_matches_both_workspace_and_user(db_session, member_context):
    workspace, users = member_context
    other = workspace_service.create_workspace(db_session, "Other", users["outsider"].id)
    member = workspace_members_service.get_workspace_member(db_session, workspace.id, users["owner"].id)
    assert member.workspace_id == workspace.id
    assert member.user_id == users["owner"].id
    assert workspace_members_service.get_workspace_member(db_session, workspace.id, users["outsider"].id) is None
    assert workspace_members_service.get_workspace_member(db_session, other.id, users["owner"].id) is None


def test_add_rolls_back_and_reraises_write_failure(db_session, member_context, monkeypatch):
    workspace, users = member_context
    workspace_id, owner_id, email = workspace.id, users["owner"].id, users["target"].email
    before = membership_ids(db_session)
    failure = RuntimeError("Simulated commit failure")

    def fail_commit():
        db_session.flush()
        raise failure

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError) as error:
        workspace_members_service.add_workspace_member(
            db_session, workspace_id, email, RoleEnum.viewer, owner_id,
        )
    assert error.value is failure
    assert membership_ids(db_session) == before
