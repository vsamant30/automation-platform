from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.core.security import hash_password
from app.db.models import Base, User


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


@pytest.fixture(autouse=True)
def prepare_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """
    Create a clean temporary database for every test.

    The application's SessionLocal is replaced only while the test runs.
    The real automation_platform.db database is not used.
    """

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        TestSessionLocal,
    )

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(main_module.app) as test_client:
        yield test_client


def create_test_user(
    username: str,
    password: str,
    role: str = "admin",
    is_active: bool = True,
) -> None:
    db: Session = TestSessionLocal()

    try:
        user = User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )

        db.add(user)
        db.commit()

    finally:
        db.close()


def test_valid_login_redirects_to_dashboard(
    client: TestClient,
) -> None:
    create_test_user(
        username="testadmin",
        password="TestPassword123!",
    )

    response = client.post(
        "/login-page",
        data={
            "username": "testadmin",
            "password": "TestPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert "access_token" in response.cookies


def test_invalid_password_returns_401(
    client: TestClient,
) -> None:
    create_test_user(
        username="testadmin",
        password="CorrectPassword123!",
    )

    response = client.post(
        "/login-page",
        data={
            "username": "testadmin",
            "password": "WrongPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_unknown_user_returns_401(
    client: TestClient,
) -> None:
    response = client.post(
        "/login-page",
        data={
            "username": "unknown-user",
            "password": "AnyPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_inactive_user_returns_403(
    client: TestClient,
) -> None:
    create_test_user(
        username="inactive-user",
        password="TestPassword123!",
        is_active=False,
    )

    response = client.post(
        "/login-page",
        data={
            "username": "inactive-user",
            "password": "TestPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "Your account is inactive" in response.text


def test_logout_removes_access_token_cookie(
    client: TestClient,
) -> None:
    response = client.get(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login-page"
    assert "access_token" in response.headers.get(
        "set-cookie",
        "",
    )