"""Exercise PostgreSQL constraints on model-created AND Alembic-created tables.

These tests deliberately import every model. They do not verify application
startup model discovery; run configure_mappers in a fresh process for that.
"""
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, insert, inspect, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.user import User
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember

U = User.__table__
W = Workspace.__table__
M = WorkspaceMember.__table__


@pytest.fixture(scope="session")
def migrated_engine(db_url):
    """Run the real migration chain with a search_path excluding public."""
    admin = create_engine(db_url)
    schema = f"pytest_migrations_{uuid4().hex}"
    created = False
    try:
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        created = True
        url = make_url(db_url).update_query_dict({"options": f"-csearch_path={schema}"})
        env = os.environ.copy()
        env["DATABASE_URL"] = url.render_as_string(hide_password=False)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        yield admin.execution_options(schema_translate_map={None: schema})
    finally:
        try:
            if created:
                with admin.begin() as conn:
                    # Only the unique schema created by this fixture is removed.
                    conn.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


@pytest.fixture(params=["models", "migrations"])
def workspace_session(request):
    engine = request.getfixturevalue("db_engine" if request.param == "models" else "migrated_engine")
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            tx.rollback()


@pytest.fixture
def parents(workspace_session):
    db = workspace_session
    user_id = db.execute(insert(U).values(
        name="Constraint test", email=f"{uuid4().hex}@example.com",
        password="not-used-for-authentication",
    ).returning(U.c.id)).scalar_one()
    workspace_id = db.execute(insert(W).values(name="Constraint test").returning(W.c.id)).scalar_one()
    return user_id, workspace_id


def membership(db, parents, **overrides):
    user_id, workspace_id = parents
    values = dict(user_id=user_id, workspace_id=workspace_id, role="viewer")
    values.update(overrides)
    return db.execute(insert(M).values(**values).returning(M.c.id)).scalar_one()


def rejected(db, statement, sqlstate):
    with pytest.raises((IntegrityError, DataError)) as error:
        with db.begin_nested():
            db.execute(statement)
    assert error.value.orig.pgcode == sqlstate


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
def test_allowed_roles(workspace_session, parents, role):
    member_id = membership(workspace_session, parents, role=role)
    assert workspace_session.scalar(select(M.c.role).where(M.c.id == member_id)) == role


@pytest.mark.parametrize("role", ["admin", "OWNER", "", " owner "])
def test_invalid_roles_rejected(workspace_session, parents, role):
    user_id, workspace_id = parents
    rejected(workspace_session, insert(M).values(user_id=user_id, workspace_id=workspace_id, role=role), "23514")


def test_invalid_role_update_rejected(workspace_session, parents):
    member_id = membership(workspace_session, parents)
    rejected(workspace_session, update(M).where(M.c.id == member_id).values(role="admin"), "23514")


def test_duplicate_membership_rejected(workspace_session, parents):
    membership(workspace_session, parents)
    user_id, workspace_id = parents
    rejected(workspace_session, insert(M).values(user_id=user_id, workspace_id=workspace_id, role="owner"), "23505")


@pytest.mark.parametrize("field", ["user_id", "workspace_id"])
def test_missing_parent_rejected(workspace_session, parents, field):
    values = dict(user_id=parents[0], workspace_id=parents[1], role="viewer")
    values[field] = -1
    rejected(workspace_session, insert(M).values(**values), "23503")


@pytest.mark.parametrize("field", ["user_id", "workspace_id", "role", "joined_at", "updated_at"])
def test_membership_not_null(workspace_session, parents, field):
    values = dict(user_id=parents[0], workspace_id=parents[1], role="viewer")
    values[field] = None
    rejected(workspace_session, insert(M).values(**values), "23502")


@pytest.mark.parametrize("field", ["name", "created_at", "updated_at"])
def test_workspace_not_null(workspace_session, field):
    values = {"name": "Test", field: None}
    rejected(workspace_session, insert(W).values(**values), "23502")


def test_workspace_name_length(workspace_session):
    workspace_session.execute(insert(W).values(name="x" * 255))
    rejected(workspace_session, insert(W).values(name="x" * 256), "22001")


def test_primary_keys_reject_duplicates(workspace_session, parents):
    member_id = membership(workspace_session, parents)
    rejected(workspace_session, insert(W).values(id=parents[1], name="Duplicate ID"), "23505")
    rejected(workspace_session, insert(M).values(id=member_id, user_id=parents[0], workspace_id=parents[1], role="viewer"), "23505")


def test_identity_and_timestamp_defaults(workspace_session, parents):
    db = workspace_session
    member_id = membership(db, parents)
    workspace_id2 = db.execute(insert(W).values(name="Second").returning(W.c.id)).scalar_one()
    member_id2 = membership(db, (parents[0], workspace_id2))
    assert workspace_id2 > parents[1]
    assert member_id2 > member_id
    schema = db.get_bind().get_execution_options()["schema_translate_map"][None]
    inspector = inspect(db.connection())
    for table in ["users", "workspaces", "workspace_members"]:
        columns = inspector.get_columns(table, schema=schema)
        identity = next(c for c in columns if c["name"] == "id")["identity"]
        assert identity["always"] is False
    row = db.execute(select(W).where(W.c.id == parents[1])).mappings().one()
    assert row["created_at"] is not None and row["updated_at"] is not None
    row = db.execute(select(M).where(M.c.id == member_id)).mappings().one()
    assert row["joined_at"] is not None and row["updated_at"] is not None


@pytest.mark.parametrize("parent", ["user", "workspace"])
@pytest.mark.parametrize("method", ["database", "orm"])
def test_parent_deletion_removes_memberships_only(workspace_session, parents, parent, method):
    db = workspace_session
    member_id = membership(db, parents)
    user2 = db.execute(insert(U).values(name="Other", email=f"{uuid4().hex}@example.com", password="unused").returning(U.c.id)).scalar_one()
    workspace2 = db.execute(insert(W).values(name="Other").returning(W.c.id)).scalar_one()
    unrelated_member = membership(db, (user2, workspace2))
    # Also connect each parent to another record to exercise multi-row cascades.
    membership(db, (parents[0], workspace2))
    membership(db, (user2, parents[1]))
    model, key = (User, parents[0]) if parent == "user" else (Workspace, parents[1])
    if method == "orm":
        db.delete(db.get(model, key))
        db.flush()
    else:
        # Core DELETE bypasses ORM relationship cascade entirely.
        db.execute(delete(model.__table__).where(model.__table__.c.id == key))
    assert db.scalar(select(M.c.id).where(M.c.id == member_id)) is None
    fk = M.c.user_id if parent == "user" else M.c.workspace_id
    assert db.execute(select(M.c.id).where(fk == key)).all() == []
    assert db.scalar(select(M.c.id).where(M.c.id == unrelated_member)) == unrelated_member
    survivor, survivor_id = (W, parents[1]) if parent == "user" else (U, parents[0])
    assert db.scalar(select(survivor.c.id).where(survivor.c.id == survivor_id)) == survivor_id


def test_deleting_membership_preserves_parents(workspace_session, parents):
    db = workspace_session
    member_id = membership(db, parents)
    db.execute(delete(M).where(M.c.id == member_id))
    assert db.scalar(select(U.c.id).where(U.c.id == parents[0])) == parents[0]
    assert db.scalar(select(W.c.id).where(W.c.id == parents[1])) == parents[1]


@pytest.mark.parametrize("parent", ["user", "workspace"])
def test_removing_relationship_deletes_orphan(workspace_session, parents, parent):
    db = workspace_session
    member_id = membership(db, parents)
    model, key = (User, parents[0]) if parent == "user" else (Workspace, parents[1])
    owner = db.get(model, key)
    owner.workspace_members.remove(db.get(WorkspaceMember, member_id))
    db.flush()
    assert db.scalar(select(M.c.id).where(M.c.id == member_id)) is None
    assert db.scalar(select(U.c.id).where(U.c.id == parents[0])) == parents[0]
    assert db.scalar(select(W.c.id).where(W.c.id == parents[1])) == parents[1]


def test_constraints_do_not_enforce_single_owner(workspace_session, parents):
    """Document current behavior: multiple owners are allowed by this schema."""
    db = workspace_session
    membership(db, parents, role="owner")
    user2 = db.execute(insert(U).values(name="Other owner", email=f"{uuid4().hex}@example.com", password="unused").returning(U.c.id)).scalar_one()
    membership(db, (user2, parents[1]), role="owner")
    assert len(db.execute(select(M.c.id).where(M.c.workspace_id == parents[1], M.c.role == "owner")).all()) == 2
