from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.mail import views

router = DefaultRouter()
router.register("mail/mailboxes", views.MailboxViewSet, basename="mailbox")
router.register("mail/threads", views.ThreadViewSet, basename="mail-thread")
router.register("mail/drafts", views.DraftViewSet, basename="mail-draft")
router.register("mail/templates", views.TemplateViewSet, basename="mail-template")

urlpatterns = [
    path("mail/setup-status", views.MailboxViewSet.as_view({"get": "setup_status"})),
    path("mail/connect/<str:provider>", views.MailboxViewSet.as_view({"post": "connect"})),
    path(
        "mail/connect/<str:provider>/callback",
        views.MailboxViewSet.as_view({"get": "connect_callback"}),
    ),
    path(
        "mail/style-guide",
        views.StyleGuideViewSet.as_view({"get": "retrieve_guide", "put": "update_guide"}),
    ),
    path("mail/review-queue", views.DraftViewSet.as_view({"get": "review_queue"})),
    path("mail/metrics", views.DraftViewSet.as_view({"get": "metrics"})),
    *router.urls,
]
