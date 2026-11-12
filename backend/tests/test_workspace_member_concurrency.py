"""Exercise real PostgreSQL locks with independent sessions and committed data."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.database import Base
from app.models.user import User
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember
from app.schemas.workspace_members import RoleEnum
from app.services.exceptions import ExistingMemberError, NotFoundError, NotOwnerError
from app.services.workspace_members_service import add_workspace_member


@pytest.fixture
def concurrent_context(db_engine):
    # Real commits are required: the regular db_session savepoint fixture
    # deliberately keeps its data invisible to other connections.
    schema = f"pytest_concurrency_{uuid4().hex}"
    with db_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = db_engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            users = [User(name=f"User {i}", email=f"{uuid4().hex}@example.com", password="unused")
                     for i in range(5)]
            workspace = Workspace(name="Concurrent members")
            db.add_all([workspace, *users])
            db.flush()
            db.add_all([
                WorkspaceMember(workspace_id=workspace.id, user_id=users[0].id, role="owner"),
                WorkspaceMember(workspace_id=workspace.id, user_id=users[1].id, role="owner"),
                WorkspaceMember(workspace_id=workspace.id, user_id=users[2].id, role="viewer"),
            ])
            db.commit()
            context = (engine, workspace.id, [(user.id, user.email) for user in users])
        yield context
    finally:
        with db_engine.begin() as connection:
            # Remove only the UUID schema created by this fixture.
            connection.execute(DropSchema(schema, cascade=True))


def prepare_connection(connection):
    connection.execute(text("SET statement_timeout = '10s'"))
    pid = connection.scalar(text("SELECT pg_backend_pid()"))
    connection.commit()
    return pid


def wait_for_blocker(engine, waiter_pid, blocker_pid, future):
    """Verify database-reported blocking, rather than infer it from a sleep."""
    deadline = monotonic() + 5
    with engine.connect() as observer:
        while monotonic() < deadline:
            blockers = observer.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter_pid}
            )
            if blocker_pid in blockers:
                return
            assert not future.done(), "Second request completed without waiting for the workspace lock"
            Event().wait(0.02)
    pytest.fail("Second request did not wait for the first request's database lock")


@pytest.mark.parametrize("scenario", ["same_target", "different_targets", "first_write_fails"])
def test_concurrent_adds_wait_and_recheck_membership(concurrent_context, scenario):
    engine, workspace_id, users = concurrent_context
    first_locked, release_first, second_started = Event(), Event(), Event()
    pids = {}

    def add(index):
        # Each worker owns its connection/session; ORM sessions are never shared.
        with engine.connect() as connection:
            pids[index] = prepare_connection(connection)

            def hold_first_lock(conn, cursor, statement, parameters, context, executemany):
                if "FOR UPDATE" in statement.upper():
                    first_locked.set()
                    assert release_first.wait(8), "Timed out waiting to release first request"

            if index == 0:
                event.listen(connection, "after_cursor_execute", hold_first_lock)
            try:
                with Session(connection) as db:
                    if index == 0 and scenario == "first_write_fails":
                        def fail_commit():
                            db.flush()
                            raise RuntimeError("Simulated write failure")
                        db.commit = fail_commit
                    if index == 1:
                        second_started.set()
                    target = users[4] if index == 1 and scenario == "different_targets" else users[3]
                    try:
                        member = add_workspace_member(
                            db, workspace_id, target[1], RoleEnum.viewer, users[index][0]
                        )
                        return ("added", member.user_id)
                    except ExistingMemberError:
                        return ("duplicate", target[0])
                    except RuntimeError as exc:
                        if str(exc) != "Simulated write failure":
                            raise
                        return ("rolled_back", target[0])
            finally:
                if index == 0:
                    event.remove(connection, "after_cursor_execute", hold_first_lock)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(add, 0)
        try:
            assert first_locked.wait(5), "First request did not acquire a workspace lock"
            second = pool.submit(add, 1)
            assert second_started.wait(5)
            assert pids[0] != pids[1]
            wait_for_blocker(engine, pids[1], pids[0], second)
        finally:
            # Always unblock workers, even when an assertion fails.
            release_first.set()
        first_result, second_result = first.result(timeout=12), second.result(timeout=12)

    if scenario == "same_target":
        assert first_result == ("added", users[3][0])
        assert second_result == ("duplicate", users[3][0])
    elif scenario == "different_targets":
        assert first_result == ("added", users[3][0])
        assert second_result == ("added", users[4][0])
    else:
        assert first_result == ("rolled_back", users[3][0])
        assert second_result == ("added", users[3][0])

    with Session(engine) as db:
        members = db.scalars(select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id.in_([users[3][0], users[4][0]]),
        )).all()
        expected_ids = [users[3][0], users[4][0]] if scenario == "different_targets" else [users[3][0]]
        assert sorted(member.user_id for member in members) == sorted(expected_ids)
        assert all(member.role == "viewer" for member in members)


@pytest.mark.parametrize("actor_index,error", [(2, NotOwnerError), (4, NotFoundError)])
def test_permission_error_releases_lock_before_session_closes(concurrent_context, actor_index, error):
    engine, workspace_id, users = concurrent_context
    with engine.connect() as rejected_connection, engine.connect() as next_connection:
        prepare_connection(rejected_connection)
        prepare_connection(next_connection)
        with Session(rejected_connection) as rejected, Session(next_connection) as following:
            with pytest.raises(error):
                add_workspace_member(
                    rejected, workspace_id, users[3][1], RoleEnum.viewer, users[actor_index][0]
                )
            # Keep the rejected session open: closing it would hide a missing rollback.
            following.execute(select(Workspace).where(
                Workspace.id == workspace_id
            ).with_for_update(nowait=True)).scalar_one()
            member = add_workspace_member(
                following, workspace_id, users[3][1], RoleEnum.viewer, users[0][0]
            )
            assert member.user_id == users[3][0]
