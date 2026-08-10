from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Job
from app.main import app


main_module = importlib.import_module(
    "app.main"
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

client = TestClient(
    app,
    raise_server_exceptions=False,
)


@pytest.fixture(autouse=True)
def prepare_upload_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[Path, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    upload_directory = (
        tmp_path
        / "uploads"
    )

    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        TestSessionLocal,
    )

    monkeypatch.setattr(
        main_module,
        "UPLOAD_DIRECTORY",
        str(upload_directory),
    )

    monkeypatch.setattr(
        main_module,
        "get_current_user_from_cookie",
        lambda request, db: SimpleNamespace(
            id=1,
            username="upload-admin",
            role="admin",
        ),
    )

    yield upload_directory

    Base.metadata.drop_all(bind=test_engine)


def count_jobs() -> int:
    db = TestSessionLocal()

    try:
        return db.query(Job).count()

    finally:
        db.close()


def test_valid_upload_creates_job_and_script(
    prepare_upload_test: Path,
) -> None:
    response = client.post(
        "/upload-script",
        data={
            "job_name": "Upload Route Test",
            "description": (
                "Created through the upload endpoint"
            ),
            "script_type": "python",
        },
        files={
            "script_file": (
                "route_test.py",
                b"print('route test passed')\n",
                "text/x-python",
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert count_jobs() == 1

    db = TestSessionLocal()

    try:
        job = db.query(Job).one()

        assert job.name == "Upload Route Test"
        assert job.script_type == "python"
        assert job.script_path

        stored_script = Path(
            job.script_path
        )

        assert stored_script.parent == (
            prepare_upload_test
        )
        assert stored_script.read_bytes() == (
            b"print('route test passed')\n"
        )

    finally:
        db.close()


def test_rejected_upload_creates_nothing(
    prepare_upload_test: Path,
) -> None:
    response = client.post(
        "/upload-script",
        data={
            "job_name": "Rejected Upload Test",
            "description": "Binary content",
            "script_type": "python",
        },
        files={
            "script_file": (
                "rejected.py",
                b"\x00\x01\x02",
                "application/octet-stream",
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert count_jobs() == 0

    assert (
        not prepare_upload_test.exists()
        or not list(
            prepare_upload_test.iterdir()
        )
    )


def test_failed_database_operation_removes_script(
    prepare_upload_test: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_audit_logging(**kwargs) -> None:
        raise RuntimeError(
            "Simulated audit failure"
        )

    monkeypatch.setattr(
        main_module,
        "log_audit_event",
        fail_audit_logging,
    )

    response = client.post(
        "/upload-script",
        data={
            "job_name": "Cleanup Upload Test",
            "description": "Must be rolled back",
            "script_type": "python",
        },
        files={
            "script_file": (
                "cleanup_test.py",
                b"print('must be removed')\n",
                "text/x-python",
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 500
    assert count_jobs() == 0
    assert prepare_upload_test.exists()
    assert not list(
        prepare_upload_test.iterdir()
    )