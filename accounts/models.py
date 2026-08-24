import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class Organization(models.Model):
    """
    契約組織（ブレイブワークの導入先企業）。技術設計書 2.3節 organizations に対応。
    サービス利用契約の単位。将来の1組織複数ユーザー対応を見据え User と分離してある。
    """

    PLAN_FREE = "free"
    PLAN_PRO = "pro"
    PLAN_CHOICES = [
        (PLAN_FREE, "FREE"),
        (PLAN_PRO, "PRO"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField("会社名", max_length=255)
    own_website_url = models.URLField("自社HP URL", max_length=500, blank=True)
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default=PLAN_FREE)
    # PRO版：月間AI解析上限件数（将来用。今回のFREE版では未使用）
    pro_ai_quota_monthly = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "契約組織"
        verbose_name_plural = "契約組織"

    def __str__(self):
        return self.company_name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("メールアドレスは必須です")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.ROLE_ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    ログインユーザー（担当者）。技術設計書 2.3節 users に対応。
    1組織に複数担当者を将来的に追加できるよう Organization と分離している。
    """

    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [(ROLE_ADMIN, "管理者")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="users", verbose_name="所属組織"
    )
    name = models.CharField("担当者名", max_length=100)
    email = models.EmailField("メールアドレス", unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name


class NotificationSettings(models.Model):
    """
    通知設定（組織ごと1件）。技術設計書 2.3節 notification_settings に対応。
    """

    FREQ_INSTANT = "instant"
    FREQ_DAILY = "daily"
    FREQ_WEEKLY = "weekly"
    FREQ_CHOICES = [
        (FREQ_INSTANT, "即時通知"),
        (FREQ_DAILY, "1日1回まとめ（未実装）"),
        (FREQ_WEEKLY, "週1回まとめ（未実装）"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="notification_settings"
    )
    notify_email = models.EmailField("通知先メールアドレス")
    alert_threshold_score = models.PositiveSmallIntegerField("メール通知する最低スコア", default=80)
    watch_threshold_score = models.PositiveSmallIntegerField("要チェック表示の最低スコア", default=60)
    notify_frequency = models.CharField(max_length=20, choices=FREQ_CHOICES, default=FREQ_INSTANT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "通知設定"
        verbose_name_plural = "通知設定"

    def __str__(self):
        return f"通知設定({self.organization.company_name})"
