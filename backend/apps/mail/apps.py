from django.apps import AppConfig


class MailConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mail"

    def ready(self) -> None:
        # Registers the party-merge handler that reassigns EmailThread.party.
        import apps.mail.services.party_resolution  # noqa: F401
