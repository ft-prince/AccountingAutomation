from django.urls import path

from apps.reporting.views import ReportView

urlpatterns = [path("reports/<slug:name>", ReportView.as_view(), name="report")]
