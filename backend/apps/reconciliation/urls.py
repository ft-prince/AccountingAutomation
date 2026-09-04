from rest_framework.routers import DefaultRouter

from apps.reconciliation import views

router = DefaultRouter()
# Sub-resources first so "reconciliation/matches/" is not swallowed by the batch detail route.
router.register("reconciliation/matches", views.MatchViewSet, basename="reconciliation-match")
router.register("reconciliation/records", views.RecordViewSet, basename="reconciliation-record")
router.register("reconciliation", views.BatchViewSet, basename="reconciliation-batch")
urlpatterns = router.urls
