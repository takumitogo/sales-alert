from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from intel.models import Alert, WebDocument


@login_required
def index_view(request):
    org = request.user.organization
    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)

    companies_qs = org.companies.all()
    monitored_count = companies_qs.filter(monitoring_enabled=True).count()

    week_docs = WebDocument.objects.filter(company__organization=org, first_detected_at__gte=week_ago)
    week_doc_count = week_docs.count()

    week_alerts = Alert.objects.filter(organization=org, created_at__gte=week_ago)
    week_alert_count = week_alerts.filter(alert_level=Alert.LEVEL_ALERT).count()
    week_watch_count = week_alerts.filter(alert_level=Alert.LEVEL_WATCH).count()

    recent_alerts = (
        Alert.objects.filter(organization=org, alert_level__in=[Alert.LEVEL_ALERT, Alert.LEVEL_WATCH])
        .select_related("company", "web_document")
        .order_by("-created_at")[:20]
    )

    return render(request, "dashboard/index.html", {
        "monitored_count": monitored_count,
        "week_doc_count": week_doc_count,
        "week_alert_count": week_alert_count,
        "week_watch_count": week_watch_count,
        "recent_alerts": recent_alerts,
    })
