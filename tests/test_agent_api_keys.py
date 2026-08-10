from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.security import verify_agent_api_key
from app.db.models import Agent, Base
from app.main import app
from app.services import agent_service


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def prepare_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        agent_service,
        "SessionLocal",
        TestSessionLocal,
    )

    previous_user_override = (
        app.dependency_overrides.get(
            get_current_user
        )
    )

    yield

    if previous_user_override is None:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

    else:
        app.dependency_overrides[
            get_current_user
        ] = previous_user_override

    Base.metadata.drop_all(bind=test_engine)


def override_authenticated_user(
    role: str,
) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: SimpleNamespace(
        role=role
    )


def create_test_agent() -> Agent:
    db = TestSessionLocal()

    try:
        agent = Agent(
            name="API Key Test Agent",
            platform="windows",
            hostname="test-host",
            base_url="http://test-agent",
            status="Offline",
            is_enabled=True,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        return agent

    finally:
        db.close()


def test_admin_can_provision_agent_api_key() -> None:
    override_authenticated_user(
        role="admin"
    )

    agent = create_test_agent()

    response = client.post(
        f"/api/v1/agents/{agent.id}/api-key/rotate"
    )

    assert response.status_code == 200

    response_data = response.json()["data"]

    assert response_data["agent_id"] == agent.id
    assert response_data["api_key"]

    db = TestSessionLocal()

    try:
        stored_agent = db.get(
            Agent,
            agent.id,
        )

        assert stored_agent is not None
        assert stored_agent.api_key_hash
        assert (
            stored_agent.api_key_hash
            != response_data["api_key"]
        )
        assert verify_agent_api_key(
            response_data["api_key"],
            stored_agent.api_key_hash,
        )

    finally:
        db.close()


def test_non_admin_cannot_provision_agent_api_key() -> None:
    override_authenticated_user(
        role="user"
    )

    agent = create_test_agent()

    response = client.post(
        f"/api/v1/agents/{agent.id}/api-key/rotate"
    )

    assert response.status_code == 403


def test_unknown_agent_returns_not_found() -> None:
    override_authenticated_user(
        role="admin"
    )

    response = client.post(
        "/api/v1/agents/99999/api-key/rotate"
    )

    assert response.status_code == 404


def test_rotation_invalidates_previous_api_key() -> None:
    override_authenticated_user(
        role="admin"
    )

    agent = create_test_agent()

    first_response = client.post(
        f"/api/v1/agents/{agent.id}/api-key/rotate"
    )

    second_response = client.post(
        f"/api/v1/agents/{agent.id}/api-key/rotate"
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_key = first_response.json()["data"]["api_key"]
    second_key = second_response.json()["data"]["api_key"]

    assert first_key != second_key

    db = TestSessionLocal()

    try:
        stored_agent = db.get(
            Agent,
            agent.id,
        )

        assert stored_agent is not None
        assert stored_agent.api_key_hash

        assert not verify_agent_api_key(
            first_key,
            stored_agent.api_key_hash,
        )

        assert verify_agent_api_key(
            second_key,
            stored_agent.api_key_hash,
        )

    finally:
        db.close()