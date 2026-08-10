from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import create_access_token
from app.core.security import hash_password
from app.db.database import get_db
from app.db.models import Base, Job, User
from app.main import app


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def prepare_test_database() -> Generator[None, None, None]:
    """
    Create a clean temporary database before every test.

    This does not modify automation_platform.db.
    """

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    client.cookies.clear()

    yield

    client.cookies.clear()
    Base.metadata.drop_all(bind=test_engine)


def create_test_user(
    username: str,
    role: str = "admin",
    is_active: bool = True,
) -> User:
    db = TestSessionLocal()

    try:
        user = User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=hash_password("TestPassword123!"),
            role=role,
            is_active=is_active,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def create_test_job(
    name: str,
    is_enabled: bool = True,
) -> Job:
    db = TestSessionLocal()

    try:
        job = Job(
            name=name,
            status="Pending",
            is_enabled=is_enabled,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return job

    finally:
        db.close()


def bearer_headers(
    username: str,
    role: str = "admin",
) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": username,
            "role": role,
        }
    )

    return {
        "Authorization": f"Bearer {token}",
    }


def test_get_jobs_requires_authentication() -> None:
    response = client.get("/jobs/")

    assert response.status_code in (401, 403)


def test_admin_can_create_job() -> None:
    create_test_user(
        username="testadmin",
        role="admin",
    )

    response = client.post(
        "/jobs/",
        json={
            "name": "Test Automation Job",
            "is_enabled": True,
        },
        headers=bearer_headers(
            username="testadmin",
            role="admin",
        ),
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["name"] == "Test Automation Job"
    assert response_data["status"] == "Pending"
    assert response_data["is_enabled"] is True
    assert response_data["id"] > 0


def test_non_admin_cannot_create_job() -> None:
    create_test_user(
        username="standard-user",
        role="user",
    )

    response = client.post(
        "/jobs/",
        json={
            "name": "Unauthorized Job",
            "is_enabled": True,
        },
        headers=bearer_headers(
            username="standard-user",
            role="user",
        ),
    )

    assert response.status_code == 403


def test_authenticated_user_can_list_jobs() -> None:
    create_test_user(
        username="testadmin",
        role="admin",
    )

    create_test_job(
        name="First Test Job",
    )

    create_test_job(
        name="Second Test Job",
        is_enabled=False,
    )

    response = client.get(
        "/jobs/",
        headers=bearer_headers(
            username="testadmin",
            role="admin",
        ),
    )

    assert response.status_code == 200

    response_data = response.json()

    assert len(response_data) == 2
    assert response_data[0]["name"] == "First Test Job"
    assert response_data[1]["name"] == "Second Test Job"
    assert response_data[1]["is_enabled"] is False


def test_admin_can_disable_job_using_cookie() -> None:
    create_test_user(
        username="testadmin",
        role="admin",
    )

    job = create_test_job(
        name="Enabled Test Job",
        is_enabled=True,
    )

    token = create_access_token(
        {
            "sub": "testadmin",
            "role": "admin",
        }
    )

    client.cookies.set(
        "access_token",
        token,
    )

    response = client.put(
        f"/jobs/{job.id}/toggle",
        headers={
            "Origin": "http://testserver",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["job_id"] == job.id
    assert response_data["is_enabled"] is False
    assert response_data["message"] == "Job disabled"


def test_toggle_unknown_job_returns_404() -> None:
    create_test_user(
        username="testadmin",
        role="admin",
    )

    token = create_access_token(
        {
            "sub": "testadmin",
            "role": "admin",
        }
    )

    client.cookies.set(
        "access_token",
        token,
    )

    response = client.put(
        "/jobs/99999/toggle",
        headers={
            "Origin": "http://testserver",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
