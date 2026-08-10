from collections.abc import Generator
import importlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_authenticated_agent_id
from app.core.security import hash_agent_api_key
from app.db.models import Agent, Base
from app.main import app
from app.services import agent_service


auth_module = importlib.import_module(
    "app.core.auth"
)

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

authentication_test_app = FastAPI()


@authentication_test_app.post(
    "/agent-protected"
)
def agent_protected_route(
    agent_id: int = Depends(
        get_authenticated_agent_id
    ),
) -> dict[str, int]:
    return {
        "agent_id": agent_id,
    }


authentication_client = TestClient(
    authentication_test_app
)

platform_client = TestClient(app)


@pytest.fixture(autouse=True)
def prepare_authentication_test(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        agent_service,
        "SessionLocal",
        TestSessionLocal,
    )

    previous_override = (
        app.dependency_overrides.get(
            get_authenticated_agent_id
        )
    )

    yield

    if previous_override is None:
        app.dependency_overrides.pop(
            get_authenticated_agent_id,
            None,
        )

    else:
        app.dependency_overrides[
            get_authenticated_agent_id
        ] = previous_override

    Base.metadata.drop_all(bind=test_engine)


def create_agent(
    *,
    api_key: str,
    is_enabled: bool,
) -> Agent:
    db = TestSessionLocal()

    try:
        agent = Agent(
            name=(
                "Enabled Agent"
                if is_enabled
                else "Disabled Agent"
            ),
            platform="windows",
            hostname="authentication-host",
            base_url="http://authentication-agent",
            api_key_hash=hash_agent_api_key(
                api_key
            ),
            status="Offline",
            is_enabled=is_enabled,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        return agent

    finally:
        db.close()


def test_missing_agent_headers_are_rejected() -> None:
    response = authentication_client.post(
        "/agent-protected"
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid Agent credentials."
    )


def test_incorrect_agent_api_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_module,
        "verify_agent_credentials",
        lambda agent_id, api_key: False,
    )

    response = authentication_client.post(
        "/agent-protected",
        headers={
            "X-Agent-ID": "1",
            "X-Agent-API-Key": "incorrect-key",
        },
    )

    assert response.status_code == 401


def test_disabled_agent_credentials_are_rejected() -> None:
    api_key = "disabled-agent-api-key"

    agent = create_agent(
        api_key=api_key,
        is_enabled=False,
    )

    assert not agent_service.verify_agent_credentials(
        agent.id,
        api_key,
    )


def test_valid_agent_credentials_are_accepted() -> None:
    api_key = "enabled-agent-api-key"

    agent = create_agent(
        api_key=api_key,
        is_enabled=True,
    )

    assert agent_service.verify_agent_credentials(
        agent.id,
        api_key,
    )


def test_authenticated_agent_id_must_match_route() -> None:
    app.dependency_overrides[
        get_authenticated_agent_id
    ] = lambda: 1

    response = platform_client.post(
        "/api/v1/agents/2/heartbeat",
        json={
            "hostname": "mismatched-host",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Agent ID does not match authenticated Agent."
    )