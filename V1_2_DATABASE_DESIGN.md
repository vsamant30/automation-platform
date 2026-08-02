# Automation Platform v1.2 Database Design

Project: Automation Platform
Version: 1.2
Status: Design Phase

---

# Existing Tables

Current production tables:

1. users
2. jobs
3. job_executions

These tables are stable and must remain backward compatible.

---

# Database Design Principles

- Never modify existing data unnecessarily.
- Never drop production tables.
- Use migration scripts for every schema change.
- Keep SQLite compatibility.
- Maintain backward compatibility with v1.1.
- Add only required columns.
- New features should use new tables whenever possible.

---

# Proposed Database Changes

## Existing Tables

users
- No planned changes

jobs
- Keep existing structure
- Future optional metadata fields may be added through migrations

job_executions
- Keep existing structure
- Additional tracking fields may be added in future releases

---

# New Tables Planned

## audit_logs

Purpose:

Store every important platform activity.

Examples:

- User login
- User logout
- Job creation
- Job update
- Job deletion
- Manual execution
- Scheduled execution
- Retry execution
- Scheduler events
- System events

---

Possible Columns

id

event_type

job_id

username

message

status

created_at

---

## notification_queue

Purpose:

Queue notifications before delivery.

Possible Columns

id

event_type

recipient

subject

message

status

created_at

sent_at

---

## system_settings

Purpose:

Store configurable platform settings.

Examples

Scheduler interval

Execution timeout

Retry count

Retention days

UI preferences

---

Possible Columns

id

setting_name

setting_value

description

updated_at

---

# Migration Strategy

Every schema change will follow:

1. Inspect database
2. Check if table exists
3. Check if column exists
4. Apply migration only if required
5. Print success message
6. Never modify existing data

---

# Phase 2 Deliverables

✓ Database Design

✓ Migration Strategy

Pending

Audit Log Model

Audit Log Migration

Audit Service

Notification Queue

Settings Table

---

Last Updated

02-Aug-2026