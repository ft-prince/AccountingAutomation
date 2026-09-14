from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.payments import views

router = DefaultRouter()
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("bank/accounts", views.BankAccountViewSet, basename="bank-account")
router.register("bank/balance-snapshots", views.SnapshotViewSet, basename="bank-snapshot")
router.register("bank/transactions", views.TransactionViewSet, basename="bank-txn")
router.register("bank/statements", views.ImportViewSet, basename="bank-import")

urlpatterns = [
    path("bank/statements/import", views.TransactionViewSet.as_view({"post": "import_statement"})),
    path("bank/auto-match", views.TransactionViewSet.as_view({"post": "auto_match"})),
    *router.urls,
]
