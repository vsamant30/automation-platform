# Automation Platform v2.0 — Current Handover

## Current status

Automation Platform v2.0 is a functional FastAPI-based automation orchestration system. The current development baseline is the `develop-v2.0` branch.

Verified baseline:

- 94 automated tests pass.
- The test run completes without warnings.
- Browser mutations have CSRF protection.
- Uploaded scripts are validated and failed uploads are cleaned up.
- Scheduled execution uses the common execution service.
- Remote executions are represented in standard execution history.
- Agent API keys can be provisioned and rotated.
- Production mode requires an explicitly configured `SECRET_KEY`.
- Hard-coded default administrative credentials have been removed.

## What the system does

The platform lets authenticated administrators create, upload, configure, schedule, execute, monitor, and audit automation jobs. Jobs can execute on the application host or through registered remote agents. The interface provides dashboard status, execution history, detailed output and errors, workflow dependencies, agent monitoring, application settings, and audit records.

Supported uploaded script types are Python, PowerShell, and Windows batch scripts.

## Architecture

The system is organized into these primary layers:

1. **FastAPI application and browser routes** — `app/main.py` serves HTML pages, browser actions, health endpoints, and application startup/shutdown behavior.
2. **Versioned REST API** — modules under `app/api/` expose authentication, users, jobs, agents, and remote-agent job operations.
3. **Service layer** — modules under `app/services/` implement execution, agents, remote jobs, audit logging, email notification, secret storage, and upload validation.
4. **Scheduler** — `app/scheduler/` synchronizes persisted schedules with APScheduler and invokes the common job-execution path.
5. **Persistence** — SQLAlchemy models and database setup under `app/db/` store users, jobs, executions, audit records, settings, agents, remote jobs, and remote logs.
6. **Remote agents** — platform-specific implementations under `agents/windows_agent/`, `agents/linux_agent/`, and `agents/macos_agent/` poll for work, download scripts, execute them, and report status and logs.
7. **Presentation layer** — Jinja templates under `app/templates/` and shared assets under `app/static/` provide the administrative interface.

## End-to-end execution flows

### Manual local execution

1. An authenticated user selects **Run**.
2. The browser request is authenticated and protected by the browser CSRF policy.
3. The job is loaded and validated.
4. The common execution service creates a `JobExecution` record.
5. The configured script is executed with the interpreter appropriate to its script type.
6. Standard output, errors, timing, result, and final status are persisted.
7. Job status and duration are updated.
8. Configured completion or failure notifications are evaluated.
9. Dashboard, job details, and execution history display the same persisted result.

### Scheduled execution

1. Schedule configuration is stored on the job.
2. Scheduler synchronization registers or removes the corresponding APScheduler task.
3. At the due time, the scheduler invokes the common execution service.
4. Dependency and conditional-execution rules are evaluated.
5. A matching job executes through the same history, status, error, and notification path as a manual run.
6. A non-matching condition creates a skipped execution record with its reason.

### Remote-agent execution

1. An administrator queues a job for a registered, enabled agent.
2. An `AgentJob` queue record is created.
3. The agent authenticates using its agent ID and API key, sends heartbeats, and claims assigned work.
4. The agent downloads the script, selects the correct interpreter, executes it, and streams or submits logs.
5. Completion or failure updates the remote queue record.
6. The platform creates or updates the corresponding standard execution-history record so remote activity appears alongside local and scheduled executions.
7. Temporary downloaded scripts are removed by the agent after execution.

### Upload flow

1. An authenticated administrator submits job metadata and a script.
2. The upload validator checks the declared script type, filename, extension, size, encoding, content, and empty-file conditions.
3. Rejected content creates neither a job nor a persisted script.
4. Accepted content is written using a generated safe filename and a job is created.
5. If database creation fails after writing, the script file is removed.

## Authentication and security

- Browser and REST authentication use JWT access tokens.
- Browser sessions use the access-token cookie.
- Browser state-changing requests are subject to same-origin CSRF validation.
- Agent endpoints use separately provisioned agent API keys.
- Rotating an agent key invalidates the previous key.
- Disabled agents and mismatched agent identities are rejected.
- `ENVIRONMENT=production` requires a configured `SECRET_KEY`; startup fails if it is absent.
- Development may generate a temporary secret, which invalidates sessions after restart.
- Administrative users are created interactively; credentials are not embedded in source code.
- SMTP passwords and other supported secrets may be resolved through the configured secret provider.

## Configuration

Primary environment configuration includes:

- `ENVIRONMENT`
- `APP_NAME`
- `APP_VERSION`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `SECRET_PROVIDER`
- Azure Key Vault, AWS Secrets Manager, or Vault provider settings where applicable
- SMTP and email-notification defaults

Application-level email settings can also be managed through the administrative settings page and persisted in the database.

## Persisted data

The default database is the local SQLite file `automation_platform.db`. It contains application records including users, jobs, execution history, audit logs, application settings, agents, remote job queue entries, and agent logs.

Other runtime data includes:

- Uploaded scripts in the configured uploads directory.
- Application and execution logs in their configured log locations.
- Windows-agent encrypted API-key material under `C:\ProgramData\AutomationPlatform\` when using the Windows secret store.

A temporary Cloudflare URL is only a network tunnel. It does not move the database, scripts, or credentials into Cloudflare storage.

## Startup and recovery

Application lifecycle handling uses FastAPI lifespan management. Startup initializes database state, performs interrupted-execution recovery, synchronizes schedules, and starts scheduler operation. Shutdown stops scheduler resources cleanly.

Executions left running by an application restart are marked failed with an explanatory interruption message rather than remaining indefinitely active.

## Error handling

Important handled cases include:

- Missing script files.
- Unsupported, mismatched, oversized, binary, invalid-UTF-8, empty, or path-like uploads.
- Database failures after a script has been written.
- Duplicate or overlapping execution protection.
- Dependency and condition mismatches.
- Interrupted executions during restart.
- Missing or invalid browser authentication.
- Missing, incorrect, disabled, or mismatched agent credentials.
- Remote interpreter and script-execution failures.
- Job deletion blocked when local or remote history must be preserved.

Failures are persisted with status and error details for inspection through execution history and detail pages.

## Automated verification

The current suite contains 94 passing tests across authentication, authorization, jobs, deletion protection, scheduling synchronization and execution, CSRF, configuration security, upload validation and route cleanup, agent authentication and API-key provisioning, Windows-agent interpreter selection, remote execution history, and failure-state consistency.

Run the complete suite from the repository root:

```powershell
python -m pytest -q
```

## Documentation relationship

- `README.md` is the current operational entry point.
- This file is the current v2.0 architecture and handover record.
- `FINAL_V1_1_TEST_CHECKLIST.md` and the `V1_2_*` files are retained as historical planning and release artifacts. They should not be interpreted as the current implementation state.
- The older Word handover and historical screenshots describe the earlier delivered UI and baseline. The application implementation and current Markdown documentation are authoritative when they differ.

## Deployment facts not verified by the repository

The following depend on the target environment and cannot be guaranteed from source code alone:

- Public DNS and permanent production hostname.
- TLS termination and reverse-proxy configuration.
- Firewall and network segmentation.
- Production database selection, capacity, retention, and restoration testing.
- Service-account permissions and operating-system hardening.
- Availability targets, load limits, and concurrent execution capacity.
- External email and secret-provider credentials.

## Recommended release procedure

1. Confirm the working tree contains only intended changes.
2. Run `git diff --check`.
3. Run `python -m pytest -q` and require all tests to pass.
4. Set production environment variables, especially `ENVIRONMENT=production` and a persistent `SECRET_KEY`.
5. Back up the database, uploads, relevant logs, and agent secret material.
6. Build a versioned release archive from a clean commit.
7. Deploy behind a permanent HTTPS endpoint.
8. Perform login, upload, manual execution, scheduling, remote execution, history, audit, notification, and restore smoke tests.

## Optional future work

No known high-priority correctness or security item from the completed improvement list remains. Useful future operational work includes permanent production hosting, CI/CD, automated and tested backups, database migration tooling for larger deployments, centralized observability, performance/load testing, and periodic dependency/security review.
