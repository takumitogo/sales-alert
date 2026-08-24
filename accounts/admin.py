from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import NotificationSettings, Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "plan", "created_at")
    search_fields = ("company_name",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("email", "name", "organization", "role", "is_active", "is_staff")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("個人情報", {"fields": ("name", "organization", "role")}),
        ("権限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "organization", "password1", "password2"),
        }),
    )
    search_fields = ("email", "name")
    filter_horizontal = ("groups", "user_permissions")


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("organization", "notify_email", "alert_threshold_score", "watch_threshold_score")
