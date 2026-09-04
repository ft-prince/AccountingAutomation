from django.urls import path

from apps.gst.views import ExportView

urlpatterns = [path("exports/<slug:kind>", ExportView.as_view(), name="export")]
