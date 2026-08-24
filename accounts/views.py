from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render

from intel.bootstrap import seed_defaults_for_organization

from .forms import EmailAuthenticationForm, NotificationSettingsForm, OrganizationAccountForm, RegistrationForm
from .models import NotificationSettings, Organization, User


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                organization = Organization.objects.create(
                    company_name=data["company_name"],
                    own_website_url=data["own_website_url"] or "",
                )
                user = User.objects.create_user(
                    email=data["email"],
                    password=data["password"],
                    name=data["name"],
                    organization=organization,
                )
                NotificationSettings.objects.create(
                    organization=organization,
                    notify_email=data["email"],
                )
                seed_defaults_for_organization(organization)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "登録が完了しました。まずは監視したい企業を登録してください。")
            return redirect("companies:list")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm


@login_required
def settings_account_view(request):
    organization = request.user.organization
    if request.method == "POST":
        form = OrganizationAccountForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, "アカウント情報を更新しました。")
            return redirect("accounts:settings_account")
    else:
        form = OrganizationAccountForm(instance=organization)
    return render(request, "accounts/settings_account.html", {"form": form})


@login_required
def settings_alerts_view(request):
    settings_obj, _ = NotificationSettings.objects.get_or_create(
        organization=request.user.organization,
        defaults={"notify_email": request.user.email},
    )
    if request.method == "POST":
        form = NotificationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "アラート設定を更新しました。")
            return redirect("accounts:settings_alerts")
    else:
        form = NotificationSettingsForm(instance=settings_obj)
    return render(request, "accounts/settings_alerts.html", {"form": form})
