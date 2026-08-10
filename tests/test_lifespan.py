import asyncio

from app import main


def test_lifespan_runs_startup_actions_in_order(
    monkeypatch,
) -> None:
    startup_actions: list[str] = []

    monkeypatch.setattr(
        main.Base.metadata,
        "create_all",
        lambda *, bind: startup_actions.append(
            "create_tables"
        ),
    )
    monkeypatch.setattr(
        main,
        "recover_interrupted_executions",
        lambda: startup_actions.append(
            "recover_executions"
        ),
    )
    monkeypatch.setattr(
        main,
        "start_scheduler",
        lambda: startup_actions.append(
            "start_scheduler"
        ),
    )

    async def run_lifespan() -> None:
        async with main.lifespan(main.app):
            startup_actions.append("serving")

    asyncio.run(run_lifespan())

    assert startup_actions == [
        "create_tables",
        "recover_executions",
        "start_scheduler",
        "serving",
    ]
