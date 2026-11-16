"""Verify document metadata against model-created and Alembic-created tables."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.models.documents import Document
from app.models.user import User
from app.models.workspaces import Workspace
# Reuse the isolated migration engine and parametrized transaction fixtures.
from tests.test_workspace_constraints import migrated_engine, workspace_session


@pytest.fixture
def document_parents(workspace_session):
    db = workspace_session
    users = [db.execute(insert(User.__table__).values(
        name="Uploader", email=f"{uuid4().hex}@example.com", password="unused",
    ).returning(User.id)).scalar_one() for _ in range(2)]
    workspaces = [db.execute(insert(Workspace.__table__).values(
        name="Documents",
    ).returning(Workspace.id)).scalar_one() for _ in range(2)]
    return users, workspaces


def add_document(db, workspace_id, uploaded_by, **overrides):
    values = dict(name="report.pdf", file_type="pdf", file_size=128,
                  storage_key=f"documents/{uuid4().hex}",
                  workspace_id=workspace_id, uploaded_by=uploaded_by)
    values.update(overrides)
    return db.execute(insert(Document.__table__).values(**values).returning(Document.id)).scalar_one()


@pytest.mark.parametrize("file_type", ["docx", "PDF", "", " pdf ", "png"])
def test_invalid_file_types_rejected(workspace_session, document_parents, file_type):
    db = workspace_session
    users, workspaces = document_parents
    with pytest.raises(IntegrityError) as error:
        with db.begin_nested():
            add_document(db, workspaces[0], users[0], file_type=file_type)
    assert error.value.orig.pgcode == "23514"
    assert error.value.orig.diag.constraint_name == "ck_file_type"
    assert db.scalars(select(Document.id)).all() == []


@pytest.mark.parametrize("file_size", [0, -1, -1024])
def test_nonpositive_file_sizes_rejected(workspace_session, document_parents, file_size):
    db = workspace_session
    users, workspaces = document_parents
    with pytest.raises(IntegrityError) as error:
        with db.begin_nested():
            add_document(db, workspaces[0], users[0], file_size=file_size)
    assert error.value.orig.pgcode == "23514"
    assert error.value.orig.diag.constraint_name == "ck_file_size"
    assert db.scalars(select(Document.id)).all() == []


@pytest.mark.parametrize("field", ["workspace_id", "uploaded_by"])
def test_nonexistent_document_references_rejected(workspace_session, document_parents, field):
    db = workspace_session
    users, workspaces = document_parents
    workspace_id = -1 if field == "workspace_id" else workspaces[0]
    uploaded_by = -1 if field == "uploaded_by" else users[0]
    with pytest.raises(IntegrityError) as error:
        with db.begin_nested():
            add_document(db, workspace_id, uploaded_by)
    assert error.value.orig.pgcode == "23503"
    assert error.value.orig.diag.constraint_name == f"documents_{field}_fkey"
    assert db.scalars(select(Document.id)).all() == []


@pytest.mark.parametrize("file_type", ["pdf", "txt", "md"])
def test_supported_types_and_minimum_size_allowed(workspace_session, document_parents, file_type):
    db = workspace_session
    users, workspaces = document_parents
    document_id = add_document(db, workspaces[0], users[0], file_type=file_type, file_size=1)
    row = db.execute(select(Document.file_type, Document.file_size).where(Document.id == document_id)).one()
    assert tuple(row) == (file_type, 1)


def test_null_uploader_allowed(workspace_session, document_parents):
    db = workspace_session
    _, workspaces = document_parents
    document_id = add_document(db, workspaces[0], None)
    row = db.execute(select(Document.id, Document.uploaded_by).where(Document.id == document_id)).one()
    assert tuple(row) == (document_id, None)


@pytest.mark.parametrize("same_workspace", [True, False])
def test_duplicate_original_filenames_allowed(workspace_session, document_parents, same_workspace):
    db = workspace_session
    users, workspaces = document_parents
    first = add_document(db, workspaces[0], users[0])
    second = add_document(db, workspaces[0 if same_workspace else 1], users[1])
    rows = db.execute(select(Document.__table__).where(Document.id.in_([first, second]))).mappings().all()
    assert len(rows) == 2
    assert {row["name"] for row in rows} == {"report.pdf"}
    assert len({row["storage_key"] for row in rows}) == 2


@pytest.mark.parametrize("same_workspace", [True, False])
def test_storage_keys_unique_across_workspaces(workspace_session, document_parents, same_workspace):
    db = workspace_session
    users, workspaces = document_parents
    key = f"documents/{uuid4().hex}"
    first = add_document(db, workspaces[0], users[0], storage_key=key)
    with pytest.raises(IntegrityError) as error:
        with db.begin_nested():
            add_document(db, workspaces[0 if same_workspace else 1], users[1],
                         name="different.pdf", storage_key=key)
    assert error.value.orig.pgcode == "23505"
    assert error.value.orig.diag.table_name == "documents"
    assert error.value.orig.diag.constraint_name == "documents_storage_key_key"
    assert db.scalars(select(Document.id).where(Document.storage_key == key)).all() == [first]


@pytest.mark.parametrize("method", ["database", "orm_unloaded", "orm_loaded"])
def test_workspace_deletion_cascades_document_metadata(workspace_session, document_parents, method):
    db = workspace_session
    users, workspaces = document_parents
    removed = [add_document(db, workspaces[0], user_id) for user_id in users]
    survivor = add_document(db, workspaces[1], users[0])
    if method == "database":
        db.execute(delete(Workspace.__table__).where(Workspace.id == workspaces[0]))
    else:
        workspace = db.get(Workspace, workspaces[0])
        if method == "orm_loaded":
            assert len(workspace.documents) == 2
        db.delete(workspace)
        db.flush()
    assert db.scalars(select(Document.id).where(Document.id.in_(removed))).all() == []
    assert db.scalar(select(Document.id).where(Document.id == survivor)) == survivor
    assert db.scalars(select(User.id).where(User.id.in_(users))).all() == users
    assert db.scalar(select(Workspace.id).where(Workspace.id == workspaces[1])) == workspaces[1]


@pytest.mark.parametrize("method", ["database", "orm_unloaded", "orm_loaded"])
def test_user_deletion_preserves_documents_and_nulls_uploader(workspace_session, document_parents, method):
    db = workspace_session
    users, workspaces = document_parents
    affected = [add_document(db, workspace_id, users[0]) for workspace_id in workspaces]
    unrelated = add_document(db, workspaces[0], users[1])
    before = db.execute(select(Document.__table__).where(Document.id.in_(affected))).mappings().all()
    if method == "database":
        db.execute(delete(User.__table__).where(User.id == users[0]))
    else:
        user = db.get(User, users[0])
        if method == "orm_loaded":
            assert len(user.documents) == 2
        db.delete(user)
        db.flush()
    after = db.execute(select(Document.__table__).where(Document.id.in_(affected))).mappings().all()
    assert {row["id"]: dict(row) for row in after} == {
        row["id"]: {**dict(row), "uploaded_by": None} for row in before
    }
    assert db.scalar(select(Document.uploaded_by).where(Document.id == unrelated)) == users[1]
    assert db.scalars(select(Workspace.id).where(Workspace.id.in_(workspaces))).all() == workspaces
