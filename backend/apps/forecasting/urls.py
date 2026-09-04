from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.forecasting import views

router = DefaultRouter()
router.register("forecast/runs", views.ForecastRunViewSet, basename="forecast-run")
router.register("forecast/scenarios", views.ScenarioViewSet, basename="forecast-scenario")
router.register("forecast/recurring", views.RecurringPatternViewSet, basename="forecast-recurring")
router.register("forecast/fixed-lines", views.FixedLineViewSet, basename="forecast-fixed-line")
router.register("forecast/expected", views.ExpectedInvoiceViewSet, basename="forecast-expected")

urlpatterns = [
    path("forecast/run", views.ForecastRunViewSet.as_view({"post": "run"})),
    path("forecast/latest", views.ForecastRunViewSet.as_view({"get": "latest"})),
    path("forecast/drivers", views.ForecastRunViewSet.as_view({"get": "drivers"})),
    path(
        "forecast/runs/<uuid:pk>/narrative",
        views.ForecastRunViewSet.as_view({"post": "narrative"}),
    ),
    path("forecast/backtest", views.ForecastRunViewSet.as_view({"get": "backtest"})),
    path("forecast/scenarios/<uuid:pk>/run", views.ScenarioViewSet.as_view({"post": "run"})),
    path(
        "forecast/risk/customers",
        views.ForecastAnalyticsViewSet.as_view({"get": "customers"}),
    ),
    path("forecast/anomalies", views.ForecastAnalyticsViewSet.as_view({"get": "anomalies"})),
    *router.urls,
]
