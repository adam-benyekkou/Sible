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
        apobj.add(settings.apprise_url)
        apobj.notify(body=message, title=title)

    def send_playbook_notification(self, playbook_name: str, status: str):
        settings = self.settings_service.get_settings()
        if (status == "success" and settings.notify_on_success) or (status == "failed" and settings.notify_on_failure):
            emoji = "✅" if status == "success" else "🚨"
            self.send_notification(f"{emoji} Playbook '{playbook_name}' finished with status: {status.upper()}", title=f"Sible: {playbook_name}")
