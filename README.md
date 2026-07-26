# Automation Platform

A local web-based automation job management platform built using FastAPI, SQLAlchemy, SQLite, APScheduler, and Jinja2.

The platform allows users to upload automation scripts, execute them manually, schedule recurring executions, view execution history, inspect console output, and download execution logs.

## Features

- Upload Python, PowerShell, and Batch scripts
- Create and manage automation jobs
- Execute jobs manually
- Schedule recurring job executions
- Interval, hourly, daily, weekly, and cron scheduling
- View job details and current status
- Track execution history
- View console output and errors
- Generate execution logs automatically
- Download execution log files
- Responsive web dashboard

## Technology Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- APScheduler
- Jinja2
- HTML
- CSS
- Uvicorn

## Project Structure

```text
Automation-Platform/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── jobs/
│   ├── models/
│   ├── scheduler/
│   ├── schemas/
│   ├── services/
│   ├── templates/
│   ├── __init__.py
│   └── main.py
├── create_db.py
├── migrate_add_job_columns.py
├── update_existing_jobs.py
├── requirements.txt
├── .gitignore
└── README.md