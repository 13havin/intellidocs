from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.core.tokens import create_access_token
from app.models.user import User
from app.models.workspace_members import WorkspaceMember
from app.schemas.workspace_members import RoleEnum
from app.services import workspace_members_service, workspace_service
from app.services.exceptions import ExistingMemberError


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


@pytest.mark.parametrize("target", ["editor", "viewer", "second_owner"])
def test_owner_removes_member(member_client, db_session, member_context, target):
    workspace, users = member_context
    target_user = users["editor" if target == "second_owner" else target]
    member = workspace_members_service.get_workspace_member(db_session, workspace.id, target_user.id)
    if target == "second_owner":
        member.role = "owner"
        db_session.commit()
    workspace_id, target_id = workspace.id, target_user.id
    before = membership_ids(db_session)
    removed_id = member.id
    response = member_client.delete(
        f"{endpoint(workspace_id)}/{target_id}", headers=headers(users["owner"]),
    )
    assert response.status_code == 204, response.text
    assert response.content == b""
    db_session.rollback()
    db_session.expunge_all()
    assert membership_ids(db_session) == before - {removed_id}
    assert db_session.get(User, target_id) is not None
    owners = db_session.scalars(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role == "owner",
    )).all()
    assert len(owners) == 1


@pytest.mark.parametrize("use_me", [True, False])
@pytest.mark.parametrize("another_owner", [True, False])
def test_owner_self_removal_preserves_last_owner(
    member_client, db_session, member_context, use_me, another_owner
):
    workspace, users = member_context
    # Owners in other workspaces cannot make deleting this workspace's last
    # owner valid.
    workspace_service.create_workspace(db_session, "Other workspace", users["outsider"].id)
    if another_owner:
        member = workspace_members_service.get_workspace_member(db_session, workspace.id, users["editor"].id)
        member.role = "owner"
        db_session.commit()
    workspace_id, owner_id = workspace.id, users["owner"].id
    response = member_client.delete(
        f"{endpoint(workspace_id)}/{'me' if use_me else owner_id}", headers=headers(users["owner"]),
    )
    assert response.status_code == (204 if another_owner else 409)
    if another_owner:
        assert response.content == b""
    else:
        assert response.json() == {"detail": "Cannot remove the last owner of the workspace"}
    db_session.rollback()
    db_session.expunge_all()
    remaining = workspace_members_service.get_workspace_member(db_session, workspace_id, owner_id)
    assert (remaining is None) == another_owner
    assert db_session.get(User, owner_id) is not None


@pytest.mark.parametrize("actor,status", [("editor", 403), ("viewer", 403), ("outsider", 404)])
def test_removing_another_member_requires_owner(member_client, db_session, member_context, actor, status):
    workspace, users = member_context
    before = membership_ids(db_session)
    response = member_client.delete(
        f"{endpoint(workspace.id)}/{users['owner'].id}", headers=headers(users[actor]),
    )
    assert response.status_code == status
    detail = "Workspace not found" if status == 404 else "You do not have permission to perform this action"
    assert response.json() == {"detail": detail}
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("actor", ["editor", "viewer"])
@pytest.mark.parametrize("use_me", [True, False])
def test_non_owner_can_leave_workspace(member_client, db_session, member_context, actor, use_me):
    workspace, users = member_context
    workspace_id, user_id = workspace.id, users[actor].id
    member_id = workspace_members_service.get_workspace_member(db_session, workspace_id, user_id).id
    before = membership_ids(db_session)
    response = member_client.delete(
        f"{endpoint(workspace_id)}/{'me' if use_me else user_id}", headers=headers(users[actor]),
    )
    assert response.status_code == 204, response.text
    assert response.content == b""
    db_session.rollback()
    db_session.expunge_all()
    assert membership_ids(db_session) == before - {member_id}
    assert db_session.get(User, user_id) is not None


@pytest.mark.parametrize("use_me", [True, False])
def test_non_member_cannot_leave_workspace(member_client, db_session, member_context, use_me):
    workspace, users = member_context
    before = membership_ids(db_session)
    response = member_client.delete(
        f"{endpoint(workspace.id)}/{'me' if use_me else users['outsider'].id}",
        headers=headers(users["outsider"]),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "User is not a member of the workspace"}
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_target_non_member_uses_shared_handler(member_client, db_session, member_context, method):
    workspace, users = member_context
    before = membership_ids(db_session)
    kwargs = {"json": {"role": "viewer"}} if method == "PATCH" else {}
    response = member_client.request(
        method, f"{endpoint(workspace.id)}/{users['outsider'].id}", headers=headers(users["owner"]), **kwargs,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "User is not a member of the workspace"}
    assert membership_ids(db_session) == before


@pytest.mark.parametrize("suffix", ["me", "-1"])
def test_removal_requires_authentication(member_client, member_context, suffix):
    workspace, _ = member_context
    response = member_client.delete(f"{endpoint(workspace.id)}/{suffix}")
    assert response.status_code == 401


def test_removal_missing_workspace(member_client, member_context):
    _, users = member_context
    response = member_client.delete(f"{endpoint(-1)}/me", headers=headers(users["owner"]))
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


@pytest.mark.parametrize("role", ["editor", "viewer"])
def test_last_owner_cannot_demote_self(member_client, db_session, member_context, role):
    workspace, users = member_context
    # Owning a different workspace must not satisfy this workspace's policy.
    workspace_service.create_workspace(db_session, "Other", users["outsider"].id)
    workspace_id, owner_id = workspace.id, users["owner"].id
    response = member_client.patch(
        f"{endpoint(workspace_id)}/{owner_id}", headers=headers(users["owner"]),
        json={"role": role},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Cannot remove the last owner of the workspace"}
    db_session.expire_all()
    assert workspace_members_service.get_workspace_member(db_session, workspace_id, owner_id).role == "owner"


@pytest.mark.parametrize("target,role", [
    ("owner", "owner"), ("editor", "viewer"), ("viewer", "editor"), ("viewer", "owner"),
])
def test_owner_updates_member_role(member_client, db_session, member_context, target, role):
    workspace, users = member_context
    workspace_id, target_id, email = workspace.id, users[target].id, users[target].email
    response = member_client.patch(
        f"{endpoint(workspace_id)}/{target_id}", headers=headers(users["owner"]), json={"role": role},
    )
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"email", "role", "joined_at"}
    assert response.json()["email"] == email
    assert response.json()["role"] == role
    datetime.fromisoformat(response.json()["joined_at"])
    db_session.rollback()
    db_session.expunge_all()
    assert workspace_members_service.get_workspace_member(db_session, workspace_id, target_id).role == role


@pytest.mark.parametrize("role", ["editor", "viewer"])
def test_owner_can_demote_self_when_another_owner_exists(member_client, db_session, member_context, role):
    workspace, users = member_context
    other = workspace_members_service.get_workspace_member(db_session, workspace.id, users["editor"].id)
    other.role = "owner"
    db_session.commit()
    response = member_client.patch(
        f"{endpoint(workspace.id)}/{users['owner'].id}",
        headers=headers(users["owner"]), json={"role": role},
    )
    assert response.status_code == 200
    assert response.json()["role"] == role
    owners = db_session.scalars(select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.role == "owner",
    )).all()
    assert owners == [users["editor"].id]


@pytest.mark.parametrize("actor,status", [("outsider", 404), ("viewer", 403), ("editor", 403)])
@pytest.mark.parametrize("role", ["owner", "viewer"])
def test_role_update_rejects_unauthorized_users(member_client, db_session, member_context, actor, status, role):
    workspace, users = member_context
    response = member_client.patch(
        f"{endpoint(workspace.id)}/{users['viewer'].id}",
        headers=headers(users[actor]), json={"role": role},
    )
    assert response.status_code == status
    expected_detail = "Workspace not found" if status == 404 else "You do not have permission to perform this action"
    assert response.json() == {"detail": expected_detail}
    db_session.expire_all()
    assert workspace_members_service.get_workspace_member(db_session, workspace.id, users["viewer"].id).role == "viewer"


@pytest.mark.parametrize("missing", ["workspace", "membership"])
def test_role_update_requires_workspace_and_target_membership(member_client, member_context, missing):
    workspace, users = member_context
    response = member_client.patch(
        f"{endpoint(-1 if missing == 'workspace' else workspace.id)}/{users['outsider'].id}",
        headers=headers(users["owner"]), json={"role": "viewer"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("payload", [{}, {"role": "admin"}, {"role": None}])
def test_role_update_validates_payload(member_client, member_context, payload):
    workspace, users = member_context
    response = member_client.patch(
        f"{endpoint(workspace.id)}/{users['viewer'].id}",
        headers=headers(users["owner"]), json=payload,
    )
    assert response.status_code == 422


def test_role_update_requires_authentication(member_client, member_context):
    workspace, users = member_context
    response = member_client.patch(
        f"{endpoint(workspace.id)}/{users['viewer'].id}", json={"role": "owner"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
def test_same_role_returns_member_without_update_or_commit(
    member_client, db_session, member_context, monkeypatch, role
):
    workspace, users = member_context
    member = workspace_members_service.get_workspace_member(db_session, workspace.id, users[role].id)
    before = (member.role, member.joined_at, member.updated_at)
    commit = Mock(wraps=db_session.commit)
    monkeypatch.setattr(db_session, "commit", commit)
    writes = []
    connection = db_session.connection()

    def record_writes(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"UPDATE", "INSERT", "DELETE"}:
            writes.append(statement)

    event.listen(connection, "before_cursor_execute", record_writes)
    try:
        response = member_client.patch(
            f"{endpoint(workspace.id)}/{users[role].id}",
            headers=headers(users["owner"]), json={"role": role},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "email": users[role].email, "role": role, "joined_at": member.joined_at.isoformat(),
        }
        commit.assert_not_called()
        # A subsequent flush must not reveal a pending change either.
        db_session.flush()
        assert writes == []
        db_session.refresh(member)
        assert (member.role, member.joined_at, member.updated_at) == before
    finally:
        event.remove(connection, "before_cursor_execute", record_writes)


def test_role_update_rejects_non_integer_user_id(member_client, member_context):
    workspace, users = member_context
    response = member_client.patch(
        f"{endpoint(workspace.id)}/not-an-id", headers=headers(users["owner"]),
        json={"role": "viewer"},
    )
    assert response.status_code == 422
    assert any(error["loc"] == ["path", "user_id"] for error in response.json()["detail"])


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
    detail = "Workspace not found" if status == 404 else "You do not have permission to perform this action"
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


def inject_membership_constraint_failure(db, monkeypatch, kind):
    """Trigger a real database error after the service's membership pre-check."""
    original_commit = db.commit
    existing_id = db.scalar(select(WorkspaceMember.id).limit(1))
    errors = []

    def failing_commit():
        # One-shot injection so subsequent writes can verify session recovery.
        monkeypatch.setattr(db, "commit", original_commit)
        member = next(obj for obj in db.new if isinstance(obj, WorkspaceMember))
        if kind == "membership_unique":
            db.add(WorkspaceMember(
                workspace_id=member.workspace_id, user_id=member.user_id, role=member.role,
            ))
        elif kind == "primary_key":
            member.id = existing_id
        elif kind == "foreign_key":
            member.user_id = -1
        elif kind == "role_check":
            member.role = "invalid-role"
        else:
            raise AssertionError(f"Unknown failure kind: {kind}")
        try:
            original_commit()
        except IntegrityError as exc:
            errors.append(exc)
            raise

    monkeypatch.setattr(db, "commit", failing_commit)
    return errors


@pytest.mark.parametrize("kind,sqlstate,expected_error", [
    ("membership_unique", "23505", ExistingMemberError),
    ("primary_key", "23505", IntegrityError),
    ("foreign_key", "23503", IntegrityError),
    ("role_check", "23514", IntegrityError),
])
def test_add_translates_only_membership_unique_violation(
    db_session, member_context, monkeypatch, kind, sqlstate, expected_error
):
    workspace, users = member_context
    workspace_id, owner_id = workspace.id, users["owner"].id
    target_id, email = users["target"].id, users["target"].email
    before = membership_ids(db_session)
    errors = inject_membership_constraint_failure(db_session, monkeypatch, kind)

    with pytest.raises(expected_error) as caught:
        workspace_members_service.add_workspace_member(
            db_session, workspace_id, email, RoleEnum.viewer, owner_id,
        )

    assert len(errors) == 1
    assert errors[0].orig.pgcode == sqlstate
    if kind == "membership_unique":
        assert caught.value.__cause__ is errors[0]
        assert errors[0].orig.diag.constraint_name == "workspace_members_workspace_id_user_id_key"
    else:
        assert caught.value is errors[0]
    # Both inserts in the duplicate case must disappear on rollback, and
    # unrelated errors must also leave a usable session with no partial writes.
    assert membership_ids(db_session) == before
    member = workspace_members_service.add_workspace_member(
        db_session, workspace_id, email, RoleEnum.viewer, owner_id,
    )
    assert member.user_id == target_id
    assert len(membership_ids(db_session)) == len(before) + 1


def test_database_duplicate_membership_returns_409(
    member_client, db_session, member_context, monkeypatch
):
    workspace, users = member_context
    workspace_id, email = workspace.id, users["target"].email
    auth = headers(users["owner"])
    before = membership_ids(db_session)
    errors = inject_membership_constraint_failure(db_session, monkeypatch, "membership_unique")

    response = member_client.post(
        endpoint(workspace_id), headers=auth, json={"email": email, "role": "viewer"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": f"{email} is already a member of workspace"}
    assert len(errors) == 1  # Proves the database fallback, not the pre-check, ran.
    assert membership_ids(db_session) == before
