from rest_framework.routers import DefaultRouter

from apps.core.notifications import NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [*router.urls]
