from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("companies/", include("companies.urls")),
    path("intel/", include("intel.urls")),
    path("", include("dashboard.urls")),
    path("home/", RedirectView.as_view(pattern_name="dashboard:index"), name="home"),
]
