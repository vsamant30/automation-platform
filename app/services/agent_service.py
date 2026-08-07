from datetime import datetime

from app.core.security import (
    generate_agent_api_key,
    hash_agent_api_key,
    verify_agent_api_key,
)

from app.db.database import SessionLocal
from app.db.models import Agent


SUPPORTED_PLATFORMS = {
    "windows",
    "linux",
    "macos",
}


def _clean_base_url(base_url: str) -> str:
    cleaned_base_url = base_url.strip().rstrip("/")

    if not cleaned_base_url:
        raise ValueError(
            "Agent base URL is required."
        )

    if not cleaned_base_url.startswith(
        ("http://", "https://")
    ):
        raise ValueError(
            "Agent base URL must start with "
            "http:// or https://."
        )

    return cleaned_base_url


def _clean_platform(platform: str) -> str:
    cleaned_platform = platform.strip().lower()

    if cleaned_platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            "Unsupported agent platform: "
            f"{platform}"
        )

    return cleaned_platform


def get_agents() -> list[Agent]:
    """
    Return all registered agents ordered by name.
    """

    db = SessionLocal()

    try:
        agents = (
            db.query(Agent)
            .order_by(Agent.name)
            .all()
        )

        for agent in agents:
            db.expunge(agent)

        return agents

    finally:
        db.close()


def get_agent(
    agent_id: int,
) -> Agent | None:
    """
    Return one agent by ID.
    """

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is not None:
            db.expunge(agent)

        return agent

    finally:
        db.close()


def get_agent_by_name(
    name: str,
) -> Agent | None:
    """
    Return one agent by its unique name.
    """

    cleaned_name = name.strip()

    if not cleaned_name:
        return None

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.name == cleaned_name)
            .first()
        )

        if agent is not None:
            db.expunge(agent)

        return agent

    finally:
        db.close()


def create_agent(
    name: str,
    base_url: str,
    platform: str = "windows",
    hostname: str | None = None,
    api_key_hash: str | None = None,
    is_enabled: bool = True,
) -> Agent:
    """
    Register a new remote execution agent.
    """

    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError(
            "Agent name is required."
        )

    cleaned_base_url = _clean_base_url(
        base_url
    )

    cleaned_platform = _clean_platform(
        platform
    )

    cleaned_hostname = (
        hostname.strip()
        if hostname and hostname.strip()
        else None
    )

    db = SessionLocal()

    try:
        existing_agent = (
            db.query(Agent)
            .filter(Agent.name == cleaned_name)
            .first()
        )

        if existing_agent is not None:
            raise ValueError(
                f"Agent name already exists: "
                f"{cleaned_name}"
            )

        agent = Agent(
            name=cleaned_name,
            platform=cleaned_platform,
            hostname=cleaned_hostname,
            base_url=cleaned_base_url,
            api_key_hash=api_key_hash,
            status="Offline",
            is_enabled=is_enabled,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.expunge(agent)

        return agent

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_agent(
    agent_id: int,
    *,
    name: str,
    base_url: str,
    platform: str,
    hostname: str | None = None,
    is_enabled: bool = True,
) -> Agent:
    """
    Update an existing remote execution agent.
    """

    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError(
            "Agent name is required."
        )

    cleaned_base_url = _clean_base_url(
        base_url
    )

    cleaned_platform = _clean_platform(
        platform
    )

    cleaned_hostname = (
        hostname.strip()
        if hostname and hostname.strip()
        else None
    )

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            raise ValueError(
                f"Agent not found: {agent_id}"
            )

        duplicate_agent = (
            db.query(Agent)
            .filter(
                Agent.name == cleaned_name,
                Agent.id != agent_id,
            )
            .first()
        )

        if duplicate_agent is not None:
            raise ValueError(
                f"Agent name already exists: "
                f"{cleaned_name}"
            )

        agent.name = cleaned_name
        agent.platform = cleaned_platform
        agent.hostname = cleaned_hostname
        agent.base_url = cleaned_base_url
        agent.is_enabled = is_enabled

        db.commit()
        db.refresh(agent)
        db.expunge(agent)

        return agent

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def delete_agent(
    agent_id: int,
) -> bool:
    """
    Delete one registered agent.

    Return False when the agent does not exist.
    """

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            return False

        db.delete(agent)
        db.commit()

        return True

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def record_agent_heartbeat(
    agent_id: int,
    *,
    hostname: str | None = None,
) -> Agent:
    """
    Mark an enabled agent as online and update
    its most recent heartbeat timestamp.
    """

    cleaned_hostname = (
        hostname.strip()
        if hostname and hostname.strip()
        else None
    )

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            raise ValueError(
                f"Agent not found: {agent_id}"
            )

        if not agent.is_enabled:
            raise ValueError(
                f"Agent is disabled: {agent_id}"
            )

        agent.status = "Online"
        agent.last_seen_at = datetime.utcnow()

        if cleaned_hostname is not None:
            agent.hostname = cleaned_hostname

        db.commit()
        db.refresh(agent)
        db.expunge(agent)

        return agent

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_stale_agents_offline(
    *,
    stale_after_minutes: int = 5,
) -> int:
    """
    Mark agents Offline if they have not
    sent a heartbeat recently.
    """

    from datetime import timedelta

    cutoff = (
        datetime.utcnow()
        - timedelta(minutes=stale_after_minutes)
    )

    db = SessionLocal()

    try:
        updated = (
            db.query(Agent)
            .filter(
                Agent.is_enabled.is_(True),
                Agent.status == "Online",
                Agent.last_seen_at.is_not(None),
                Agent.last_seen_at < cutoff,
            )
            .update(
                {
                    Agent.status: "Offline",
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return updated

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def rotate_agent_api_key(
    agent_id: int,
) -> str:
    """
    Generate a new API key for an agent.

    Only the hash is stored in the database.
    The plaintext API key is returned once.
    """

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            raise ValueError(
                f"Agent not found: {agent_id}"
            )

        api_key = generate_agent_api_key()

        agent.api_key_hash = hash_agent_api_key(
            api_key
        )

        db.commit()

        return api_key

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def verify_agent_credentials(
    agent_id: int,
    api_key: str,
) -> bool:
    """
    Verify an enabled agent using its API key.
    """

    if not api_key or not api_key.strip():
        return False

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if (
            agent is None
            or not agent.is_enabled
            or not agent.api_key_hash
        ):
            return False

        return verify_agent_api_key(
            api_key,
            agent.api_key_hash,
        )

    finally:
        db.close()