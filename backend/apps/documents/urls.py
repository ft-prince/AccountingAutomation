from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.documents import views

router = DefaultRouter()
router.register("documents", views.DocumentViewSet, basename="document")
urlpatterns = [path("exports/documents.zip", views.DocumentsZipView.as_view()), *router.urls]
