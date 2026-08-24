from django import forms

from .models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "company_name", "hp_url", "category", "past_proposed_product",
            "lost_reason", "last_contact_date", "assigned_rep", "memo",
            "monitoring_enabled", "scan_interval_days",
        ]
        widgets = {
            "last_contact_date": forms.DateInput(attrs={"type": "date"}),
            "memo": forms.Textarea(attrs={"rows": 3}),
            "past_proposed_product": forms.Textarea(attrs={"rows": 2}),
            "lost_reason": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "company_name": "企業名", "hp_url": "企業HP URL", "category": "区分",
            "past_proposed_product": "過去提案商材", "lost_reason": "失注理由",
            "last_contact_date": "最終接触日", "assigned_rep": "担当者", "memo": "メモ",
            "monitoring_enabled": "監視ON", "scan_interval_days": "監視間隔（日）",
        }


class CsvUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSVファイル")

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("CSVファイル（.csv）を選択してください。")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("ファイルサイズは10MB以下にしてください。")
        return f


DUPLICATE_POLICY_CHOICES = [
    ("skip", "登録しない（既存データを保持）"),
    ("update", "既存データを更新する"),
]
