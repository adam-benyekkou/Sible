import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

def dismiss_security_warning(page: Page):
    """Helper to dismiss the default password warning modal if it appears."""
    dismiss_btn = page.locator('button:has-text("I\'ll Do This Later")')
    try:
        # Wait a short bit for Alpine to initialize and show the modal
        dismiss_btn.wait_for(state="visible", timeout=2000)
        dismiss_btn.click()
    except:
        pass

def test_admin_login_and_playbook_execution(page: Page):
    # 1. Login Flow
    page.goto(f"{BASE_URL}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    
    expect(page).to_have_url(f"{BASE_URL}/")
    dismiss_security_warning(page)
    
    # 2. Navigate to Playbooks
    page.click('a[href="/playbooks/dashboard"]')
    expect(page.locator("text=welcome.yml")).to_be_visible()

    # 3. Trigger Playbook Execution
    page.click('text=welcome.yml')
    
    # Wait for the editor view and click 'Run'
    page.click('button:has-text("Run")')
    
    # Launchpad Modal
    launch_btn = page.locator('button:has-text("Launch Playbook")')
    # Force wait for the modal to be visible in Alpine
    page.wait_for_selector('dialog[open]', state="visible", timeout=5000)
    expect(launch_btn).to_be_visible()
    launch_btn.click()

    # 4. WebSocket/SSE Real-Time Validation
    terminal = page.locator("#terminal-container")
    expect(terminal).to_be_visible()

    # Wait for Ansible output
    expect(terminal).to_contain_text("TASK [Display Welcome Message]", timeout=30000)
    expect(terminal).to_contain_text("Welcome to Sible", timeout=10000)
    expect(terminal).to_contain_text("Sible: Process finished with exit code 0", timeout=15000)

def test_rbac_watcher_denial(page: Page):
    # 1. Login as Watcher
    page.goto(f"{BASE_URL}/login")
    page.fill('input[name="username"]', "watcher")
    page.fill('input[name="password"]', "watcher")
    page.click('button[type="submit"]')

    expect(page).to_have_url(f"{BASE_URL}/")
    dismiss_security_warning(page)

    # 2. Navigate to Playbooks
    page.click('a[href="/playbooks/dashboard"]')
    
    # Check if Run button is hidden for watchers
    run_btn = page.locator('button:has-text("Run")')
    # Watchers shouldn't see the run button on dashboard or editor
    expect(run_btn).to_be_hidden()

def test_theme_persistence(page: Page):
    # Login
    page.goto(f"{BASE_URL}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')

    expect(page).to_have_url(f"{BASE_URL}/")
    dismiss_security_warning(page)

    # Open Settings
    page.click('a[href^="/settings/"]')
    
    # Change Theme
    with page.expect_response("**/settings/theme"):
        page.select_option('select[name="theme"]', value="dark")
    
    # Wait a bit for server-side state to persist
    page.wait_for_timeout(1000)
    
    # Refresh
    page.reload()
    dismiss_security_warning(page)
    
    expect(page.locator('select[name="theme"]')).to_have_value("dark")
