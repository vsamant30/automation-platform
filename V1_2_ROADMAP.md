# Automation Platform v1.2 Roadmap

Project: Automation Platform
Version: 1.2
Base Version: v1.1 Stable
Development Branch: develop-v1.2
Theme: Enterprise Automation and Operational Control
Status: Phase 0 In Progress

---

# Development Principles

- Build only on top of stable v1.1.
- Do not rewrite working modules.
- Do not break existing functionality.
- Work one phase at a time.
- Work one feature at a time.
- Explain architecture and design before implementation.
- Test every phase before moving forward.
- Commit only after successful validation.
- Do not modify unrelated modules.
- Keep all changes modular, maintainable, and production-ready.

---

# Phase 0 - Version Baseline and Protection

Status: In Progress

Objective:

Protect the completed v1.1 release before starting v1.2 development.

Completed:

- Confirmed main branch was clean.
- Created annotated Git tag v1.1.
- Pushed tag v1.1 to origin.
- Created branch develop-v1.2.
- Pushed develop-v1.2 to origin.

Remaining:

- Complete V1_2_ROADMAP.md.
- Record the v1.1 regression baseline.
- Commit and push Phase 0 documentation.
- Confirm develop-v1.2 working tree is clean.

Deliverables:

- Git tag: v1.1
- Branch: develop-v1.2
- Document: V1_2_ROADMAP.md
- v1.1 regression baseline

Completion target: 5 percent

---

# Phase 1 - Requirements, Architecture, and Acceptance Criteria

Status: Pending

Objective:

Define exactly what v1.2 will include before changing application code.

Scope:

- Role-Based Access Control
- Audit Logging
- Job Queue and Concurrency
- Execution Timeout
- Cancel Running or Queued Execution
- Automatic Retry
- Live Monitoring
- Notifications
- Reporting
- Security and API Hardening

Architecture decisions to define:

- Role and permission model
- Audit logging service
- Database migration approach
- Local execution queue design
- Concurrency limits
- Process termination strategy
- Retry model
- Live monitoring refresh model
- Notification service
- Reporting architecture
- Security controls

Deliverables:

- V1_2_REQUIREMENTS.md
- V1_2_ARCHITECTURE.md
- V1_2_ACCEPTANCE_CRITERIA.md

Completion target: 10 percent

---

# Phase 2 - Database and Model Design

Status: Pending

Objective:

Prepare the database safely for new enterprise features.

Planned areas:

User fields:

- role
- is_active
- last_login
- created_at
- updated_at

Audit log table:

- id
- user_id
- username
- action
- entity_type
- entity_id
- old_value
- new_value
- timestamp
- ip_address

Execution control fields:

- timeout_seconds
- retry_enabled
- max_retries
- retry_delay_seconds
- current_retry_count
- process_id
- queued_at
- cancel_requested

Job metadata:

- tags
- owner_id
- folder
- priority

Rules:

- Use migration scripts.
- Back up the database before migration.
- Test migrations on a database copy.
- Keep migrations reversible where possible.
- Do not manually modify the production database.

Deliverables:

- Database migration scripts
- Updated SQLAlchemy models
- Migration test results
- Database backup procedure

Completion target: 20 percent

---

# Phase 3 - Role-Based Access Control

Status: Pending

Objective:

Separate Admin, Operator, and Viewer permissions.

Roles:

- Admin
- Operator
- Viewer

Backend requirements:

- Add reusable permission checks.
- Protect API endpoints.
- Protect browser routes.
- Prevent direct URL bypass.
- Return proper 401 and 403 responses.

Frontend requirements:

- Hide unauthorized actions.
- Show the current user's role.
- Add access-denied handling.
- Restrict navigation items.

Required tests:

- Admin can perform all actions.
- Operator can run and schedule permitted jobs.
- Viewer can only view.
- Logged-out users are redirected to login.
- Unauthorized API access is rejected.
- Unauthorized direct URL access is rejected.

Deliverables:

- Role definitions
- Permission checks
- Protected routes
- Access-denied handling
- RBAC test suite

Completion target: 35 percent

---

# Phase 4 - Audit Logging

Status: Pending

Objective:

Record sensitive and operational activity for traceability.

Actions to capture:

- Login
- Logout
- Create job
- Upload script
- Edit job
- Delete job
- Duplicate job
- Run job
- Schedule job
- Pause schedule
- Resume schedule
- Enable job
- Disable job
- Retry execution
- Cancel execution
- Create user
- Change user role

Required audit fields:

- User
- Action
- Entity type
- Entity ID
- Old value
- New value
- Timestamp
- IP address where practical

Rules:

- Audit records must not be editable from the UI.
- Passwords and secrets must never be logged.
- Audit failures must not silently corrupt normal operations.

Deliverables:

- Audit log table
- Audit service
- Audit history page
- Filters and pagination
- CSV export
- Audit tests

Completion target: 45 percent

---

# Phase 5 - Job Queue and Concurrency Control

Status: Pending

Objective:

Prevent uncontrolled execution when multiple jobs start together.

Core features:

- Queued status
- FIFO processing
- Job priority
- Maximum concurrent executions
- Independent execution records
- Queue position
- Duplicate-click protection

Execution statuses:

- Pending
- Queued
- Running
- Completed
- Failed
- Cancelled
- Timed Out

Architecture decision:

Use a simple local queue for v1.2.

Do not introduce Redis, Celery, or distributed workers unless a real distributed requirement exists.

Deliverables:

- Queue service
- Concurrency configuration
- Queue status display
- Queue tests

Completion target: 60 percent

---

# Phase 6 - Timeout, Cancellation, and Automatic Retry

Status: Pending

Objective:

Provide operational control over long-running and failing executions.

Timeout features:

- No timeout
- Preset timeout values
- Custom timeout value
- Process termination
- Timed Out status
- Error recording
- Audit recording

Cancellation features:

- Cancel queued execution
- Cancel running execution
- Cancel button only for Queued or Running status
- Cancelled status
- Audit recording

Automatic retry features:

- Retry enabled
- Maximum retries
- Delay between retries
- Retry only on failure
- New execution record for every retry
- Link retry history
- Prevent infinite retry loops

Safeguards:

- Disabled or paused jobs must not retry unless explicitly required.
- Previous execution records must never be overwritten.

Deliverables:

- Timeout configuration
- Cancel execution feature
- Automatic retry engine
- Retry linkage
- Execution-control tests

Completion target: 72 percent

---

# Phase 7 - Live Monitoring and Dashboard Upgrade

Status: Pending

Objective:

Provide near real-time visibility into platform operations.

Dashboard additions:

- Queued jobs
- Running jobs
- Timed-out jobs
- Cancelled jobs
- Success rate
- Average duration
- Recent failures
- Next scheduled runs

Live execution details:

- Execution ID
- Current status
- Start time
- Elapsed time
- Process ID
- Live output
- Cancel button
- Retry count

Refresh strategy:

Use polling every 3 to 5 seconds for v1.2.

WebSockets or Server-Sent Events may be considered later if required.

Deliverables:

- Updated dashboard
- Live execution page
- Queue monitor
- Updated dashboard API
- Monitoring tests

Completion target: 82 percent

---

# Phase 8 - Notifications

Status: Pending

Objective:

Notify users about important execution events.

Minimum scope:

- Notify on failure
- Notify after final retry failure
- Notify on timeout
- Notify on cancellation

Optional scope:

- Notify on success
- Notify before scheduled execution
- Daily execution summary

Channel order:

1. Email
2. Microsoft Teams webhook
3. Additional integrations later

Security rules:

- Do not hard-code credentials.
- Use environment variables or an approved secret store.
- Never expose secrets in logs or the UI.

Deliverables:

- Notification service
- Email configuration
- Notification templates
- Notification history
- Notification tests

Completion target: 88 percent

---

# Phase 9 - Reporting and Operational Analytics

Status: Pending

Objective:

Provide execution trends and downloadable reports.

Reports:

- Execution summary
- Success versus failure
- Job-wise execution count
- Average duration
- Failure trends
- Frequently failing jobs
- Scheduled-job performance
- User action summary

Filters:

- Date range
- Job
- Status
- Category
- Owner
- User

Export formats:

- CSV
- Excel

PDF reporting is deferred unless specifically required.

Deliverables:

- Reports page
- Charts
- CSV export
- Excel export
- Reporting tests

Completion target: 92 percent

---

# Phase 10 - Security Hardening and API Standards

Status: Pending

Objective:

Prepare the platform for controlled deployment.

Security items:

- Secure cookies
- Session expiration
- CSRF protection
- Password policy
- Account lockout
- Rate limiting
- Input validation
- File-size limits
- File-content validation
- Safe file paths
- Secret management

API standards:

- Return 404 for missing jobs.
- Return 404 for missing executions.
- Return 401 for unauthenticated API requests.
- Return 403 for unauthorized API requests.
- Use consistent JSON error responses.
- Separate browser routes from API routes.

Upload hardening:

- Reject empty files.
- Enforce maximum file size.
- Validate extension and selected script type.
- Prevent path traversal.
- Optionally validate Python syntax during upload.

Deliverables:

- Security checklist
- Updated API error handling
- Upload limits
- Security tests

Completion target: 96 percent

---

# Phase 11 - Testing

Status: Pending

Objective:

Validate all new and impacted functionality while protecting the v1.1 baseline.

Testing types:

- Unit testing
- Feature testing
- Integration testing
- Targeted regression testing
- Negative testing
- Security testing
- Performance testing

Important integration flows:

- Upload -> Run -> Queue -> Execute -> Audit
- Schedule -> Queue -> Execute -> Notify
- Failure -> Retry -> Final Notification
- Run -> Cancel -> History -> Audit
- Timeout -> Failure Record -> Notification
- Role -> Permission -> Action Denied

Targeted v1.1 regression areas:

- Login and logout
- Dashboard
- Run
- Schedule
- Retry
- History
- Upload
- Permissions
- API endpoints

Deliverables:

- V1_2_TEST_CASES.md
- V1_2_REGRESSION_RESULTS.md
- V1_2_DEFECT_LOG.md

Completion target: 98 percent

---

# Phase 12 - Documentation and Release

Status: Pending

Objective:

Complete the v1.2 release professionally.

Required documents:

- V1_2_ROADMAP.md
- V1_2_REQUIREMENTS.md
- V1_2_ARCHITECTURE.md
- V1_2_ACCEPTANCE_CRITERIA.md
- V1_2_TEST_CASES.md
- V1_2_TEST_REPORT.md
- V1_2_RELEASE_NOTES.md
- CHANGELOG.md
- README.md

Final validation:

- No critical defects
- No unresolved high-severity defects
- Database migration tested
- Rollback documented
- Permissions validated
- Queue stable
- Timeout and cancellation verified
- Notifications verified
- Audit logging verified
- Regression passed

Release flow:

- Commit final v1.2 changes.
- Push develop-v1.2.
- Merge develop-v1.2 into main.
- Push main.
- Create annotated tag v1.2.
- Push tag v1.2.

Completion target: 100 percent

---

# Official v1.2 Scope

Included:

1. Role-Based Access Control
2. Audit Logging
3. Job Queue and Concurrency Limits
4. Execution Timeout
5. Cancel Running or Queued Execution
6. Automatic Retry
7. Live Monitoring
8. Failure Notifications
9. Improved API Status Codes
10. Upload Security Limits

Deferred:

- Advanced calendar scheduling
- Multiple schedules per job
- Full Microsoft Teams integration
- Distributed workers
- Redis or Celery
- Script version control
- PDF reporting
- Job dependencies
- Multi-server agents

---

# Current Status

Current Phase: Phase 0 - Version Baseline and Protection

Completed:

- v1.1 tag created and pushed
- develop-v1.2 branch created and pushed
- v1.1 working tree protected

Next Action:

- Validate this roadmap
- Commit Phase 0 documentation
- Push the Phase 0 commit
- Confirm clean working tree
- Start Phase 1 requirements and architecture

Last Updated: 02-Aug-2026