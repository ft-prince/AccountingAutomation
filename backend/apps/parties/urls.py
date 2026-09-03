from rest_framework.routers import DefaultRouter

from apps.parties import views

router = DefaultRouter()
router.register("parties", views.PartyViewSet, basename="party")
router.register("categories", views.CategoryViewSet, basename="category")
urlpatterns = router.urls
