import hashlib
import hmac
import secrets

from passlib.context import CryptContext


# Password hashing configuration

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def generate_agent_api_key() -> str:
    """
    Generate a cryptographically secure API key
    for a Remote Agent.
    """

    return secrets.token_urlsafe(32)


def hash_agent_api_key(
    api_key: str,
) -> str:
    """
    Return a SHA-256 hash of an Agent API key.
    """

    cleaned_api_key = api_key.strip()

    if not cleaned_api_key:
        raise ValueError(
            "Agent API key is required."
        )

    return hashlib.sha256(
        cleaned_api_key.encode("utf-8")
    ).hexdigest()


def verify_agent_api_key(
    api_key: str,
    api_key_hash: str,
) -> bool:
    """
    Verify an Agent API key against its stored hash.
    """

    cleaned_api_key = api_key.strip()
    cleaned_api_key_hash = api_key_hash.strip()

    if (
        not cleaned_api_key
        or not cleaned_api_key_hash
    ):
        return False

    calculated_hash = hash_agent_api_key(
        cleaned_api_key
    )

    return hmac.compare_digest(
        calculated_hash,
        cleaned_api_key_hash,
    )