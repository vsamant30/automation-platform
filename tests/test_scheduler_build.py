import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db.models import Job
from app.scheduler.scheduler import build_trigger


def create_job(
    schedule_type: str,
    schedule_value: str,
) -> Job:
    return Job(
        name="Scheduler Test Job",
        status="Pending",
        is_enabled=True,
        schedule_enabled=True,
        schedule_paused=False,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
    )


def test_build_interval_trigger() -> None:
    job = create_job(
        schedule_type="interval",
        schedule_value="15",
    )

    trigger = build_trigger(job)

    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 900


def test_build_hourly_trigger() -> None:
    job = create_job(
        schedule_type="hourly",
        schedule_value="00:30",
    )

    trigger = build_trigger(job)

    assert isinstance(trigger, CronTrigger)

    trigger_text = str(trigger)

    assert "minute='30'" in trigger_text


def test_build_daily_trigger() -> None:
    job = create_job(
        schedule_type="daily",
        schedule_value="14:45",
    )

    trigger = build_trigger(job)

    assert isinstance(trigger, CronTrigger)

    trigger_text = str(trigger)

    assert "hour='14'" in trigger_text
    assert "minute='45'" in trigger_text


def test_build_weekly_trigger() -> None:
    job = create_job(
        schedule_type="weekly",
        schedule_value="mon|09:15",
    )

    trigger = build_trigger(job)

    assert isinstance(trigger, CronTrigger)

    trigger_text = str(trigger)

    assert "day_of_week='mon'" in trigger_text
    assert "hour='9'" in trigger_text
    assert "minute='15'" in trigger_text


def test_build_cron_trigger() -> None:
    job = create_job(
        schedule_type="cron",
        schedule_value="0 8 * * 1-5",
    )

    trigger = build_trigger(job)

    assert isinstance(trigger, CronTrigger)

    trigger_text = str(trigger)

    assert "minute='0'" in trigger_text
    assert "hour='8'" in trigger_text
    assert "day_of_week='1-5'" in trigger_text


def test_unsupported_schedule_type_raises_error() -> None:
    job = create_job(
        schedule_type="unsupported",
        schedule_value="10",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported schedule type: unsupported",
    ):
        build_trigger(job)


@pytest.mark.parametrize(
    ("schedule_type", "schedule_value"),
    [
        ("interval", "not-a-number"),
        ("hourly", "invalid"),
        ("daily", "invalid"),
        ("weekly", "invalid"),
        ("cron", "invalid cron expression"),
    ],
)
def test_invalid_schedule_value_raises_error(
    schedule_type: str,
    schedule_value: str,
) -> None:
    job = create_job(
        schedule_type=schedule_type,
        schedule_value=schedule_value,
    )

    with pytest.raises(
        (ValueError, TypeError),
    ):
        build_trigger(job)