from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.reporting.schedule_views import ReportScheduleViewSet
from apps.reporting.views import ReportView

router = DefaultRouter()
router.register("reports/schedules", ReportScheduleViewSet, basename="report-schedule")

urlpatterns = [
    *router.urls,
    path("reports/<slug:name>", ReportView.as_view(), name="report"),
]
