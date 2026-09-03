from rest_framework.routers import DefaultRouter

from apps.documents import views

router = DefaultRouter()
router.register("documents", views.DocumentViewSet, basename="document")
urlpatterns = router.urls
