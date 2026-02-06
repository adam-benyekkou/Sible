# Implementation Plan - Phase 3: Automation (The Scheduler)

## Goal

Transform Sible from a simple runner into an Orchestrator by adding the ability to schedule Playbooks using Cron expressions.

## User Review Required
>
> [!IMPORTANT]
> The scheduler requires a persistent job store. We will use `sqlite:///jobs.sqlite` located in the root directory. This file should be persisted in Docker volumes.

## Proposed Changes

### Backend Dependencies

- **Install `apscheduler`** (`pip install apscheduler`).
- **Install `sqlalchemy`** (required for `SQLAlchemyJobStore`).

### Backend Architecture (`app/scheduler.py` & `app/main.py`)

- [NEW] `app/scheduler.py`:
  - Initialize `AsyncIOScheduler`.
  - Configure `SQLAlchemyJobStore`.
  - Define `add_job(playbook_name, cron_expression)` wrapper.
  - Define `list_jobs()` and `remove_job(job_id)`.
  - **CRITICIAL**: Define the actual function executed by the job (`execute_playbook_job`). This function must call `RunnerService` or `ansible-playbook` command directly (headless). *Challenge*: `RunnerService` yields HTML for SSE. We need a "Headless" mode for background jobs to just capture logs/exit code.

- [MODIFY] `app/main.py`:
  - Initialize Scheduler on startup (`lifespan` context manager logic, replacing current placeholder).
  - Ensure usage of proper async context.

- [MODIFY] `app/services.py` (or new logic):
  - Refactor `RunnerService.run_playbook` to allow a "headless" mode that returns status + full log string instead of yielding HTML divs? OR create a separate `BackgroundRunner` for scheduled tasks.
  - *Decision*: Create `BackgroundRunner.run_job(playbook_name)` that writes output to a file/db (Phase 5 prep) or just logs for now.

### API Routes (`app/routes.py`)

- [NEW] `POST /schedule`: Accepts JSON `{ "playbook": "foo.yaml", "cron": "*/5 * * * *" }`.
- [NEW] `GET /schedule`: Returns list of active jobs with next run time.
- [NEW] `DELETE /schedule/{job_id}`: Removes a schedule.

### Frontend UI (`templates/layout.html`, `templates/index.html`)

- [MODIFY] `templates/layout.html`: Add "Queue" link in sidebar.
- [MODIFY] `templates/index.html` (Playbook Editor):
  - Add "Schedule" button icon (Clock) in toolbar.
  - Add "Schedule Modal" (Alpine.js) with inputs for Cron.
- [NEW] `templates/queue.html`:
  - Table of scheduled jobs.
  - Columns: Playbook, Cron Schedule, Next Run, Actions (Delete).

## Verification Plan

### Automated Tests

- Test `SchedulerService.add_job` creates a job in the store.
- Test `SchedulerService.remove_job`.
- Verify `cron` parsing validity.

### Manual Verification

1. Schedule `hello.yaml` to run every minute (`* * * * *`).
2. Watch console/logs to see it execute.
3. Verify "Queue" page lists the job.
4. Delete the job and verify it stops running.
