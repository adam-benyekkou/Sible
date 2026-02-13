# Sible E2E Test Plan

## 1. Introduction
This document outlines the E2E testing strategy for Sible, focusing on validating the full lifecycle of Ansible orchestration from the HTMX frontend to real-world infrastructure execution.

## 2. Test Environment Architecture
### 2.1 The 'Test Lab'
We utilize a containerized environment defined in `docker-compose.e2e.yml`:
- **Sible Container:** The application under test.
- **Target Nodes:** Two `linuxserver/openssh-server` containers acting as managed nodes.
- **Network:** Private bridge network to ensure isolation.

### 2.2 Mocking vs. Real Execution
- **Real Execution:** Ansible playbooks MUST execute against the target nodes to verify the `RunnerService` and SSH connectivity.
- **Mocking:** External notifications (Slack/Apprise) should be mocked using a local `mailhog` or a mock API container to prevent side effects.

## 3. Critical User Journeys (CUJs)
| ID | Journey | Validation Points |
|----|---------|-------------------|
| CUJ-01 | Onboarding & Execution | Login -> Inventory View -> Run welcome.yml -> Verify logs via WebSocket |
| CUJ-02 | RBAC Enforcement | Login as 'watcher' -> Attempt Run -> Verify 403/Permission Denied partial |
| CUJ-03 | Theme Persistence | Switch Theme -> Refresh -> Verify CSS variables match theme |

## 4. WebSocket & Real-Time Validation
To verify the integrity of live logs:
- **Strategy:** Use Playwright to monitor the `#terminal` element.
- **Verification:** Assert that specific Ansible "task headers" (e.g., `TASK [Display Welcome Message]`) appear in the DOM during execution.
- **Success Criteria:** The "Execution finished" message is received and the status indicator turns green.

## 5. CI/CD Integration
- **Platform:** GitHub Actions.
- **Trigger:** Pull Requests to `main`.
- **Artifacts:** Screenshots and video traces stored on failure.
