from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.core.auth import create_access_token
from app.core.security import hash_password
from app.db.models import (
    Agent,
    AgentJob,
    AuditLog,
    Base,
    Job,
    JobExecution,
    User,
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


@pytest.fixture(autouse=True)
def prepare_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
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
def client() -> TestClient:
    return TestClient(main_module.app)


def create_admin_and_job() -> tuple[User, Job]:
    db: Session = TestSessionLocal()

    try:
        admin = User(
            username="deletion-admin",
            email="deletion-admin@example.com",
            hashed_password=hash_password(
                "TestPassword123!"
            ),
            role="admin",
            is_active=True,
        )

        job = Job(
            name="Deletion Test Job",
            category="General",
            status="Pending",
            is_enabled=True,
        )

        db.add(admin)
        db.add(job)
        db.commit()

        db.refresh(admin)
        db.refresh(job)

        admin_id = admin.id
        job_id = job.id

    finally:
        db.close()

    db = TestSessionLocal()

    try:
        admin = (
            db.query(User)
            .filter(User.id == admin_id)
            .first()
        )

        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        db.expunge(admin)
        db.expunge(job)

        return admin, job

    finally:
        db.close()


def admin_cookie() -> dict[str, str]:
    token = create_access_token(
        {
            "sub": "deletion-admin",
            "role": "admin",
        }
    )

    return {
        "access_token": token,
    }


def test_job_without_remote_history_is_deleted(
    client: TestClient,
) -> None:
    admin, job = create_admin_and_job()

    response = client.post(
        f"/dashboard/jobs/{job.id}/delete",
        cookies=admin_cookie(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/dashboard?deleted=true"
    )

    db: Session = TestSessionLocal()

    try:
        deleted_job = (
            db.query(Job)
            .filter(Job.id == job.id)
            .first()
        )

        delete_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "DELETE_JOB",
                AuditLog.entity_id == job.id,
            )
            .first()
        )

        assert deleted_job is None
        assert delete_audit is not None
        assert delete_audit.user_id == admin.id
        assert delete_audit.username == admin.username

    finally:
        db.close()


def test_job_with_remote_history_is_not_deleted(
    client: TestClient,
) -> None:
    _, job = create_admin_and_job()

    db: Session = TestSessionLocal()

    try:
        agent = Agent(
            name="Deletion Test Agent",
            platform="windows",
            hostname="test-host",
            base_url="http://127.0.0.1:9000",
            status="Offline",
            is_enabled=True,
        )

        db.add(agent)
        db.flush()

        agent_job = AgentJob(
            agent_id=agent.id,
            job_id=job.id,
            job_name=job.name,
            script_type="python",
            script_path="uploads/test_script.py",
            status="Completed",
        )

        db.add(agent_job)
        db.commit()

    finally:
        db.close()

    response = client.post(
        f"/dashboard/jobs/{job.id}/delete",
        cookies=admin_cookie(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/dashboard?delete_error=remote_history"
    )

    db = TestSessionLocal()

    try:
        protected_job = (
            db.query(Job)
            .filter(Job.id == job.id)
            .first()
        )

        delete_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "DELETE_JOB",
                AuditLog.entity_id == job.id,
            )
            .first()
        )

        assert protected_job is not None
        assert delete_audit is None

    finally:
        db.close()


def test_job_with_local_execution_history_is_not_deleted(
    client: TestClient,
) -> None:
    _, job = create_admin_and_job()

    db: Session = TestSessionLocal()

    try:
        execution = JobExecution(
            job_id=job.id,
            job_name=job.name,
            status="Completed",
            result="Historical execution result",
        )

        db.add(execution)
        db.commit()
        db.refresh(execution)

        execution_id = execution.id

    finally:
        db.close()

    response = client.post(
        f"/dashboard/jobs/{job.id}/delete",
        cookies=admin_cookie(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/dashboard?delete_error=execution_history"
    )

    db = TestSessionLocal()

    try:
        protected_job = (
            db.query(Job)
            .filter(Job.id == job.id)
            .first()
        )

        preserved_execution = (
            db.query(JobExecution)
            .filter(JobExecution.id == execution_id)
            .first()
        )

        delete_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "DELETE_JOB",
                AuditLog.entity_type == "Job",
                AuditLog.entity_id == job.id,
            )
            .first()
        )

        assert protected_job is not None
        assert preserved_execution is not None
        assert delete_audit is None

    finally:
        db.close()