from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import NotificationSettings, Organization, User


class RegistrationForm(forms.Form):
    """
    ユーザー登録フォーム。元設計書5章の必須/任意項目に対応。
    必須：会社名・担当者名・メールアドレス・パスワード／任意：自社HP URL
    """

    company_name = forms.CharField(label="会社名", max_length=255)
    own_website_url = forms.URLField(label="自社HP URL（任意）", required=False)
    name = forms.CharField(label="担当者名", max_length=100)
    email = forms.EmailField(label="メールアドレス")
    password = forms.CharField(label="パスワード", widget=forms.PasswordInput, min_length=8)
    password_confirm = forms.CharField(label="パスワード（確認）", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("このメールアドレスは既に登録されています。")
        return email

    def clean(self):
        cleaned = super().clean()
        pw, pw2 = cleaned.get("password"), cleaned.get("password_confirm")
        if pw and pw2 and pw != pw2:
            self.add_error("password_confirm", "パスワードが一致しません。")
        return cleaned


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="メールアドレス")


class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = NotificationSettings
        fields = ["notify_email", "alert_threshold_score", "watch_threshold_score"]
        labels = {
            "notify_email": "通知先メールアドレス",
            "alert_threshold_score": "メール通知する最低スコア",
            "watch_threshold_score": "「要チェック」表示の最低スコア",
        }

    def clean(self):
        cleaned = super().clean()
        alert_t = cleaned.get("alert_threshold_score")
        watch_t = cleaned.get("watch_threshold_score")
        if alert_t is not None and watch_t is not None and watch_t > alert_t:
            self.add_error("watch_threshold_score", "「要チェック」の閾値はアラート閾値以下にしてください。")
        return cleaned


class OrganizationAccountForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["company_name", "own_website_url"]
        labels = {"company_name": "会社名", "own_website_url": "自社HP URL"}
