from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts import views

router = DefaultRouter()
router.register("gstins", views.GSTINProfileViewSet, basename="gstin")
router.register("members", views.MemberViewSet, basename="member")
router.register("api-keys", views.APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("orgs/current", views.CurrentOrgView.as_view()),
    path("settings", views.SettingsView.as_view()),
    *router.urls,
]
