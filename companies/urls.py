from django.urls import path

from . import views

app_name = "companies"

urlpatterns = [
    path("", views.company_list_view, name="list"),
    path("new/", views.company_create_view, name="create"),
    path("<uuid:pk>/", views.company_detail_view, name="detail"),
    path("<uuid:pk>/edit/", views.company_edit_view, name="edit"),
    path("<uuid:pk>/toggle-monitoring/", views.company_toggle_monitoring_view, name="toggle_monitoring"),
    path("csv/upload/", views.csv_upload_view, name="csv_upload"),
    path("csv/history/", views.csv_history_view, name="csv_history"),
]
