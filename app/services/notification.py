from app.services.settings import SettingsService
from sqlmodel import Session

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)

    def send_notification(self, message: str, title: str = "Sible Alert"):
        import apprise
        settings = self.settings_service.get_settings()
        if not settings.apprise_url: return
        
        apobj = apprise.Apprise()
        
        # Support both direct service URLs (tgram://) and config URLs (http://)
        config = apprise.AppriseConfig()
        if config.add(settings.apprise_url):
            apobj.add(config)
        else:
            # Fallback to direct add if config load fails (e.g. malformed service URL)
            apobj.add(settings.apprise_url)
            
        apobj.notify(body=message, title=title)

    def send_playbook_notification(self, playbook_name: str, job):
        from app.models import PlaybookConfig
        settings = self.settings_service.get_settings()
        
        # Check for per-playbook override
        config = self.db.get(PlaybookConfig, playbook_name)
        
        status = job.status
        # Determine effective notification settings
        effective_notify_on_success = config.notify_on_success if (config and config.notify_on_success is not None) else settings.notify_on_success
        effective_notify_on_failure = config.notify_on_failure if (config and config.notify_on_failure is not None) else settings.notify_on_failure
        
        if (status == "success" and effective_notify_on_success) or (status == "failed" and effective_notify_on_failure):
            emoji = "✅" if status == "success" else "🚨"
            duration = "Unknown"
            if job.start_time and job.end_time:
                diff = job.end_time - job.start_time
                duration = str(diff).split('.')[0] # Remove microseconds
            
            msg = (
                f"{emoji} Playbook: {playbook_name}\n"
                f"Status: {status.upper()}\n"
                f"Duration: {duration}\n"
                f"Exit Code: {job.exit_code}\n"
                f"Started: {job.start_time.strftime('%Y-%m-%d %H:%M:%S') if job.start_time else 'N/A'}\n"
                f"Finished: {job.end_time.strftime('%Y-%m-%d %H:%M:%S') if job.end_time else 'N/A'}"
            )
            self.send_notification(msg, title=f"Sible: {playbook_name} [{status.upper()}]")
