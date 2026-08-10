from getpass import getpass
from secrets import compare_digest

from agents.windows_agent.secret_store import (
    load_agent_api_key,
    save_agent_api_key,
)


def provision_agent_api_key() -> None:
    api_key = getpass(
        "Paste the newly generated Agent API key: "
    ).strip()

    api_key_confirmation = getpass(
        "Paste the Agent API key again: "
    ).strip()

    if not api_key:
        raise ValueError(
            "Agent API key is required."
        )

    if not compare_digest(
        api_key,
        api_key_confirmation,
    ):
        raise ValueError(
            "Agent API key confirmation does not match."
        )

    secret_file = save_agent_api_key(
        api_key
    )

    stored_api_key = load_agent_api_key(
        secret_file
    )

    if not compare_digest(
        api_key,
        stored_api_key,
    ):
        raise RuntimeError(
            "Stored Agent API key verification failed."
        )

    print(
        "Agent API key was encrypted and stored "
        f"successfully: {secret_file}"
    )


if __name__ == "__main__":
    provision_agent_api_key()