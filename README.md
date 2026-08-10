# Automation Platform

Automation Platform is a FastAPI-based system for creating, scheduling,
executing, and auditing automation jobs. It supports local execution and
authenticated remote agents for Windows, Linux, and macOS.

## Current baseline

- Application version: **2.0.0**
- Development branch: `develop-v2.0`
- Automated regression baseline: **94 passing tests, zero warnings**
- Database: SQLite by default; configurable through `DATABASE_URL`
- API: versioned endpoints under `/api/v1` plus compatibility routes

Historical v1.1 and v1.2 planning documents remain in the repository for
traceability. They do not describe the complete current implementation.

## Capabilities

- Browser-based administration with JWT cookie authentication and RBAC
- Versioned JWT bearer-token REST API
- Python, PowerShell, Batch, and CMD script upload validation
- Manual, interval, hourly, daily, weekly, and cron execution
- Dependency and result-condition workflows
- Common execution history for local, scheduled, and remote runs
- Execution output, failure details, downloadable logs, and CSV exports
- Remote-agent registration, heartbeat, queue, claim, logs, and completion
- Per-agent API keys with administrator-controlled rotation
- Encrypted Windows-agent API-key storage
- Email notifications and database-backed SMTP settings
- Audit records containing before-and-after values
- Startup recovery for interrupted executions and stale remote work
- Responsive administration interface and interactive API documentation

## Security baseline

- Production startup requires a configured `SECRET_KEY`.
- Development generates a temporary secret when none is configured.
- Browser mutations are protected by same-origin CSRF validation.
- API operations use bearer or agent credentials rather than browser cookies.
- Uploaded scripts are checked for type, extension, filename, size, UTF-8 text,
  non-empty content, and binary content before persistence.
- Rejected uploads and database failures do not leave orphaned jobs or files.
- Administrator and user creation scripts prompt for credentials; no default
  administrator password is embedded in them.
- Agent keys are returned only when provisioned or rotated; stored server-side
  credentials are hashed.

Do not expose a development server directly to the public internet. Use HTTPS,
a stable reverse proxy or tunnel, host firewall rules, protected backups, and
operational monitoring for a production deployment.

## Architecture

```text
Browser UI / REST clients / Remote agents
                 |
                 v
        FastAPI routes and middleware
          | authentication / RBAC
          | CSRF / validation / errors
          v
   Execution, scheduling, agent, audit,
       notification, and secret services
          |                 |
          v                 v
  SQLAlchemy database   APScheduler / OS processes
          |
          v
 users, jobs, executions, audit logs,
 settings, agents, agent jobs, agent logs
```

Local manual and scheduled jobs use the common execution service. Remote agents
claim queued work, download the script, execute it on the agent host, stream
logs, and report completion. Remote completion is synchronized into standard
job execution history.

## Project layout

```text
app/
  api/          Browser-compatible and versioned REST routes
  core/         Configuration, authentication, CSRF, security, time helpers
  db/           SQLAlchemy engine and models
  scheduler/    APScheduler construction, synchronization, and recovery
  schemas/      Pydantic request and response models
  services/     Execution, agents, audit, email, secrets, upload validation
  static/       Shared CSS and JavaScript
  templates/    Jinja2 administration pages
agents/
  windows_agent/
  linux_agent/
  macos_agent/
tests/          Automated regression suite
uploads/        Runtime-managed uploaded scripts (not source-controlled)
```

## Installation

```powershell
git clone https://github.com/vsamant30/automation-platform.git
Set-Location automation-platform
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\create_db.py
python .\create_admin.py
```

The account scripts prompt for the username, email, and password.

## Required production configuration

At minimum, configure a stable secret before starting production:

```powershell
$env:ENVIRONMENT = "production"
$env:SECRET_KEY = "<long-random-secret>"
```

Supported settings include:

- `ENVIRONMENT`, `APP_NAME`, `APP_VERSION`
- `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `SECRET_PROVIDER`, `AZURE_KEY_VAULT_URL`, `AWS_REGION`
- `VAULT_ADDR`, `VAULT_NAMESPACE`, `VAULT_MOUNT_POINT`
- SMTP and email-notification variables documented in `app/core/config.py`

User-level environment variables must be loaded into the service account or
process that starts Uvicorn. A variable configured for an interactive user is
not automatically available to every Windows service account.

## Run

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Login: `http://127.0.0.1:8000/login-page`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/health`

For remote access, terminate HTTPS at a trusted reverse proxy or managed tunnel.
Cloudflare Quick Tunnel URLs are temporary and are not permanent hosting.

## Remote-agent API keys

An administrator can provision or rotate an agent key through the versioned
Agents API. After rotation, the old key is invalid. Install the returned key on
the matching agent host using its provisioning utility; do not place the clear
text key in source control or logs.

The Windows agent stores its key encrypted under the system application-data
directory. Agent identity and the route agent ID must match.

## Testing

```powershell
python -m compileall .\app .\agents .\tests
git diff --check
python -m pytest -q
```

Verified baseline at this handover: `94 passed` with no warnings.

Tests cover authentication, configuration security, CSRF, job operations,
deletion protection, scheduling, dependencies, upload validation and cleanup,
agent authentication, API-key rotation and provisioning, remote execution
history/failures, Windows interpreter selection, lifespan startup, and health.

## Runtime data and backup

By default, persistent or operational data is held in:

- `automation_platform.db` — SQLite database
- `uploads/` — uploaded automation scripts
- application and execution log locations configured by the project
- Windows agent encrypted secret file under `C:\ProgramData\AutomationPlatform`

Back up the database and uploads together while writes are quiesced, and test
restoration regularly. Git is source history, not a runtime-data backup.

## Known deployment limitations

- The default SQLite deployment is best suited to a single application host.
- The in-process APScheduler assumes one active scheduler owner; multiple
  Uvicorn workers require a deliberate distributed scheduling design.
- Permanent hosting, automated backups, monitoring, and CI/CD are deployment
  responsibilities and are not proven merely by the local test suite.
- Legacy unversioned API routes remain for compatibility.

See `CURRENT_HANDOVER_V2.0.md` for the operational handover and verified scope.

## Author

Vinayak Samant
