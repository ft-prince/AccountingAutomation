from rest_framework.routers import DefaultRouter

from apps.invoices import views

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
urlpatterns = router.urls
