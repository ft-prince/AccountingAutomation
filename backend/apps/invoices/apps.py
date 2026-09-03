from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.invoices"

    def ready(self) -> None:
        from apps.invoices import signals  # noqa: F401
