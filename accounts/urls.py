from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("settings/account/", views.settings_account_view, name="settings_account"),
    path("settings/alerts/", views.settings_alerts_view, name="settings_alerts"),
]
