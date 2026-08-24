from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Feedback, SearchKeyword, WebDocument


@login_required
def settings_keywords_view(request):
    org = request.user.organization

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            keyword = request.POST.get("keyword", "").strip()
            score = request.POST.get("score", "").strip()
            if keyword and score.isdigit():
                SearchKeyword.objects.update_or_create(
                    organization=org, keyword=keyword,
                    defaults={"score": min(int(score), 100), "enabled": True},
                )
                messages.success(request, f"キーワード「{keyword}」を追加しました。")
            else:
                messages.error(request, "キーワードと点数（数値）を入力してください。")
        elif action == "toggle":
            kw = get_object_or_404(SearchKeyword, pk=request.POST.get("keyword_id"), organization=org)
            kw.enabled = not kw.enabled
            kw.save(update_fields=["enabled", "updated_at"])
        elif action == "update_score":
            kw = get_object_or_404(SearchKeyword, pk=request.POST.get("keyword_id"), organization=org)
            score = request.POST.get("score", "").strip()
            if score.isdigit():
                kw.score = min(int(score), 100)
                kw.save(update_fields=["score", "updated_at"])
        elif action == "delete":
            SearchKeyword.objects.filter(pk=request.POST.get("keyword_id"), organization=org).delete()
        return redirect("intel:settings_keywords")

    keywords = SearchKeyword.objects.filter(organization=org).order_by("-score")
    return render(request, "intel/settings_keywords.html", {"keywords": keywords})


@login_required
def feedback_view(request, document_id):
    document = get_object_or_404(WebDocument, pk=document_id, company__organization=request.user.organization)
    rating = request.POST.get("rating")
    if rating in dict(Feedback.RATING_CHOICES):
        Feedback.objects.update_or_create(
            web_document=document, user=request.user, defaults={"rating": rating},
        )
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)
