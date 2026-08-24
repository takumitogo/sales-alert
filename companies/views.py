import base64

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .csv_utils import CATEGORY_LABEL_TO_KEY, FIELD_DEFS, decode_csv_bytes, guess_mapping, parse_csv_text
from .domain_utils import normalize_domain
from .forms import CompanyForm, CsvUploadForm, DUPLICATE_POLICY_CHOICES
from .models import Company, CsvImportBatch, CsvImportRow


@login_required
def company_list_view(request):
    org = request.user.organization
    qs = Company.objects.filter(organization=org)

    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    monitoring = request.GET.get("monitoring", "")
    min_score = request.GET.get("min_score", "")

    if q:
        qs = qs.filter(company_name__icontains=q)
    if category:
        qs = qs.filter(category=category)
    if monitoring == "on":
        qs = qs.filter(monitoring_enabled=True)
    elif monitoring == "off":
        qs = qs.filter(monitoring_enabled=False)

    qs = qs.order_by("-updated_at")

    companies_data = []
    for c in qs:
        latest_doc = c.web_documents.order_by("-first_detected_at").first()
        latest_score = latest_doc.total_score if latest_doc else None
        if min_score:
            try:
                if latest_score is None or latest_score < int(min_score):
                    continue
            except ValueError:
                pass
        companies_data.append({
            "company": c,
            "latest_score": latest_score,
            "latest_detected_at": latest_doc.first_detected_at if latest_doc else None,
            "latest_title": latest_doc.title if latest_doc else None,
        })

    paginator = Paginator(companies_data, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "companies/company_list.html", {
        "page_obj": page_obj,
        "category_choices": Company.CATEGORY_CHOICES,
        "q": q, "category": category, "monitoring": monitoring, "min_score": min_score,
    })


@login_required
def company_detail_view(request, pk):
    company = get_object_or_404(Company, pk=pk, organization=request.user.organization)
    documents = company.web_documents.order_by("-first_detected_at")
    user_feedback = {
        f.web_document_id: f.rating
        for f in request.user.feedback_entries.filter(web_document__company=company)
    }
    return render(request, "companies/company_detail.html", {
        "company": company, "documents": documents, "user_feedback": user_feedback,
    })


def _remaining_company_slots(org):
    if org.plan != org.PLAN_FREE:
        return None  # PRO版は上限なし（将来設定次第）
    return settings.FREE_PLAN_COMPANY_LIMIT - org.companies.count()


@login_required
def company_create_view(request):
    org = request.user.organization
    remaining = _remaining_company_slots(org)
    if remaining is not None and remaining <= 0:
        messages.error(
            request,
            f"FREEプランの監視企業数上限（{settings.FREE_PLAN_COMPANY_LIMIT}社）に達しています。"
            " 企業を削除するか監視OFFにしてから登録してください。",
        )
        return redirect("companies:list")
    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.organization = org
            company.domain = normalize_domain(company.hp_url)
            existing = Company.objects.filter(organization=org, domain=company.domain).first()
            if existing:
                messages.warning(
                    request,
                    f"同じドメイン（{company.domain}）の企業「{existing.company_name}」が既に登録されています。"
                    " 重複登録を避けるため保存しませんでした。既存企業を編集してください。",
                )
                return redirect("companies:detail", pk=existing.pk)
            company.save()
            messages.success(request, f"「{company.company_name}」を登録しました。")
            return redirect("companies:detail", pk=company.pk)
    else:
        form = CompanyForm(initial={"scan_interval_days": 7, "monitoring_enabled": True})
    return render(request, "companies/company_form.html", {"form": form, "is_create": True})


@login_required
def company_edit_view(request, pk):
    company = get_object_or_404(Company, pk=pk, organization=request.user.organization)
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.domain = normalize_domain(updated.hp_url)
            updated.save()
            messages.success(request, "更新しました。")
            return redirect("companies:detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)
    return render(request, "companies/company_form.html", {"form": form, "is_create": False, "company": company})


@login_required
def company_toggle_monitoring_view(request, pk):
    company = get_object_or_404(Company, pk=pk, organization=request.user.organization)
    if request.method == "POST":
        company.monitoring_enabled = not company.monitoring_enabled
        company.save(update_fields=["monitoring_enabled", "updated_at"])
    return redirect(request.META.get("HTTP_REFERER") or reverse("companies:detail", args=[pk]))


@login_required
def csv_upload_view(request):
    """
    CSV一括登録。元設計書7章の2段階フロー（アップロード→列マッピング確認→登録）。
    ファイル内容はマッピング確認画面へ base64 で受け渡し、サーバー側の一時ファイル/
    セッション管理を持たないステートレスな実装にしている（大容量ファイルは将来対応）。
    """
    org = request.user.organization

    if request.method == "POST" and "confirm_mapping" in request.POST:
        return _process_csv_import(request, org)

    if request.method == "POST":
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            raw = form.cleaned_data["csv_file"].read()
            text = decode_csv_bytes(raw)
            header, rows = parse_csv_text(text)
            if not header:
                messages.error(request, "CSVの内容を読み取れませんでした。")
                return redirect("companies:csv_upload")
            guesses = guess_mapping(header)
            csv_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            return render(request, "companies/csv_mapping.html", {
                "header": header,
                "field_defs": FIELD_DEFS,
                "guesses": guesses,
                "csv_b64": csv_b64,
                "row_count": len(rows),
                "original_filename": form.cleaned_data["csv_file"].name,
                "duplicate_policy_choices": DUPLICATE_POLICY_CHOICES,
            })
    else:
        form = CsvUploadForm()
    return render(request, "companies/csv_upload.html", {"form": form})


def _process_csv_import(request, org):
    csv_b64 = request.POST.get("csv_b64", "")
    original_filename = request.POST.get("original_filename", "upload.csv")
    duplicate_policy = request.POST.get("duplicate_policy", "skip")
    try:
        text = base64.b64decode(csv_b64).decode("utf-8")
    except Exception:
        messages.error(request, "アップロード内容の復元に失敗しました。もう一度アップロードしてください。")
        return redirect("companies:csv_upload")

    header, rows = parse_csv_text(text)
    mapping = {}
    for field_key, _label, _required, _candidates in FIELD_DEFS:
        col = request.POST.get(f"map_{field_key}", "")
        if col:
            mapping[field_key] = col

    batch = CsvImportBatch.objects.create(
        organization=org,
        uploaded_by=request.user,
        original_filename=original_filename,
        column_mapping=mapping,
        total_rows=len(rows),
        status=CsvImportBatch.STATUS_PROCESSING,
    )

    success = duplicate = error = 0
    remaining_slots = _remaining_company_slots(org)
    for i, row in enumerate(rows, start=1):
        try:
            company_name = row.get(mapping.get("company_name", ""), "").strip()
            hp_url = row.get(mapping.get("hp_url", ""), "").strip()
            if not company_name or not hp_url:
                CsvImportRow.objects.create(
                    batch=batch, row_number=i, raw_data=row,
                    result_status=CsvImportRow.RESULT_ERROR,
                    error_message="企業名またはHP URLが空です。",
                )
                error += 1
                continue

            domain = normalize_domain(hp_url)
            category_label = row.get(mapping.get("category", ""), "").strip() if mapping.get("category") else ""
            category_key = CATEGORY_LABEL_TO_KEY.get(category_label, Company.CATEGORY_OTHER)

            last_contact_raw = row.get(mapping.get("last_contact_date", ""), "").strip() if mapping.get("last_contact_date") else ""
            last_contact_date = _parse_date(last_contact_raw)

            existing = Company.objects.filter(organization=org, domain=domain).first()
            if existing:
                if duplicate_policy == "update":
                    existing.company_name = company_name
                    existing.hp_url = hp_url
                    existing.category = category_key
                    existing.past_proposed_product = row.get(mapping.get("past_proposed_product", ""), "") if mapping.get("past_proposed_product") else existing.past_proposed_product
                    existing.lost_reason = row.get(mapping.get("lost_reason", ""), "") if mapping.get("lost_reason") else existing.lost_reason
                    existing.assigned_rep = row.get(mapping.get("assigned_rep", ""), "") if mapping.get("assigned_rep") else existing.assigned_rep
                    existing.memo = row.get(mapping.get("memo", ""), "") if mapping.get("memo") else existing.memo
                    if last_contact_date:
                        existing.last_contact_date = last_contact_date
                    existing.save()
                    CsvImportRow.objects.create(
                        batch=batch, row_number=i, raw_data=row,
                        result_status=CsvImportRow.RESULT_DUPLICATE_UPDATED,
                    )
                else:
                    CsvImportRow.objects.create(
                        batch=batch, row_number=i, raw_data=row,
                        result_status=CsvImportRow.RESULT_DUPLICATE_SKIPPED,
                    )
                duplicate += 1
                continue

            if remaining_slots is not None and remaining_slots <= 0:
                CsvImportRow.objects.create(
                    batch=batch, row_number=i, raw_data=row,
                    result_status=CsvImportRow.RESULT_ERROR,
                    error_message=f"FREEプランの監視企業数上限（{settings.FREE_PLAN_COMPANY_LIMIT}社）に達したため登録できませんでした。",
                )
                error += 1
                continue

            Company.objects.create(
                organization=org,
                company_name=company_name,
                hp_url=hp_url,
                domain=domain,
                category=category_key,
                past_proposed_product=row.get(mapping.get("past_proposed_product", ""), "") if mapping.get("past_proposed_product") else "",
                lost_reason=row.get(mapping.get("lost_reason", ""), "") if mapping.get("lost_reason") else "",
                assigned_rep=row.get(mapping.get("assigned_rep", ""), "") if mapping.get("assigned_rep") else "",
                memo=row.get(mapping.get("memo", ""), "") if mapping.get("memo") else "",
                last_contact_date=last_contact_date,
            )
            CsvImportRow.objects.create(
                batch=batch, row_number=i, raw_data=row, result_status=CsvImportRow.RESULT_SUCCESS,
            )
            success += 1
            if remaining_slots is not None:
                remaining_slots -= 1
        except Exception as exc:  # 1行の失敗が全体を止めないようにする
            CsvImportRow.objects.create(
                batch=batch, row_number=i, raw_data=row,
                result_status=CsvImportRow.RESULT_ERROR, error_message=str(exc),
            )
            error += 1

    batch.success_rows = success
    batch.duplicate_rows = duplicate
    batch.error_rows = error
    batch.status = CsvImportBatch.STATUS_COMPLETED
    batch.save()

    messages.success(
        request,
        f"CSV取込が完了しました（成功 {success} 件 / 重複 {duplicate} 件 / エラー {error} 件）。",
    )
    return redirect("companies:csv_history")


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@login_required
def csv_history_view(request):
    batches = CsvImportBatch.objects.filter(organization=request.user.organization).prefetch_related("rows")
    return render(request, "companies/csv_history.html", {"batches": batches})
