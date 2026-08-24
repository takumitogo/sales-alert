from django.urls import path

from . import views

app_name = "intel"

urlpatterns = [
    path("settings/keywords/", views.settings_keywords_view, name="settings_keywords"),
    path("documents/<uuid:document_id>/feedback/", views.feedback_view, name="feedback"),
]
