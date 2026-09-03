from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.health import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.parties.urls")),
    path("api/", include("apps.documents.urls")),
    path("api/", include("apps.invoices.urls")),
    path("api/", include("apps.payments.urls")),
]

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    ]
