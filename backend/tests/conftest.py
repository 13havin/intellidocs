from pathlib import Path
import os
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

# Load test configuration before importing the application's engine or routers.
backend_dir = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or dotenv_values(
    backend_dir / "test.env"
).get("TEST_DATABASE_URL") or dotenv_values(backend_dir / ".env").get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise pytest.UsageError("Set TEST_DATABASE_URL in the environment, backend/test.env, or backend/.env.")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Test-only signing configuration, independent of local application secrets.
os.environ["SECRET_KEY"] = "intellidocs-test-signing-key-not-for-production-123456"
os.environ["ALGORITHM"] = "HS256"

from app.db.database import Base
from app.dependencies import get_db
from app.main import app


@pytest.fixture(scope="session")
def db_url():
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def db_engine(db_url):
    """Build model tables in an isolated schema without touching existing tables."""
    engine = create_engine(db_url)
    schema = f"pytest_{uuid4().hex}"
    schema_created = False
    try:
        try:
            with engine.begin() as connection:
                connection.execute(CreateSchema(schema))
            schema_created = True
        except OperationalError:
            pytest.fail("Cannot connect to TEST_DATABASE_URL. Check PostgreSQL and test database settings.", pytrace=False)

        test_engine = engine.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
    finally:
        try:
            if schema_created:
                with engine.begin() as connection:
                    # This UUID-named schema was created solely for this test run.
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Roll back each test, including changes committed by application code."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()


@pytest.fixture
def test_client(db_session):
    def override_get_db():
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def health_endpoint():
    return "/health/"


@pytest.fixture
def expected_health_response():
    return {"status": "healthy"}


@pytest.fixture
def info_endpoint():
    return "/api/v1/info/"


@pytest.fixture
def user_endpoint():
    return "/api/v1/users"


@pytest.fixture
def expected_info_response():
    return {"name": "IntelliDocs", "version": "0.1.0"}


@pytest.fixture
def user_payload_valid():
    return {
        "name": "test_user",
        "email": f"test-{uuid4().hex}@example.com",
        "password": "securepassword123"
    }


@pytest.fixture
def user_payload_invalid():
    return {"name": "test_user", "email": "testexample.com", "password": "securepassword123"}


@pytest.fixture
def registered_user(test_client, user_payload_valid):
    response = test_client.post("/auth/register", json=user_payload_valid)
    assert response.status_code == 201
    return response.json()
