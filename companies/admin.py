from django.contrib import admin

from .models import Company, CsvImportBatch, CsvImportRow


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("company_name", "domain", "category", "organization", "monitoring_enabled", "last_scanned_at")
    list_filter = ("category", "monitoring_enabled")
    search_fields = ("company_name", "domain")


class CsvImportRowInline(admin.TabularInline):
    model = CsvImportRow
    extra = 0


@admin.register(CsvImportBatch)
class CsvImportBatchAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "organization", "status", "total_rows", "success_rows", "error_rows", "created_at")
    inlines = [CsvImportRowInline]
