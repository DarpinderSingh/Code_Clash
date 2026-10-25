
from django.contrib import admin
from django.urls import include, path

from commerce.admin_views import operations_dashboard


urlpatterns = [
    # Keep this custom route before the main admin route.
    path(
        "admin/commerce/operations/",
        admin.site.admin_view(operations_dashboard),
        name="commerce-admin-operations",
    ),

    path("admin/", admin.site.urls),
    path("api/", include("commerce.urls")),
]
