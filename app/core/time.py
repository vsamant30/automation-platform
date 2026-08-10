from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return naive UTC for compatibility with existing database timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)
