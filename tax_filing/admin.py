from django.contrib import admin
from .models import TaxFiling, TaxFilingDocument, TaxCalculationLog


class TaxFilingDocumentInline(admin.TabularInline):
    model = TaxFilingDocument
    extra = 0
    readonly_fields = ['file_name', 'file_size', 'uploaded_at', 'uploaded_by']


@admin.register(TaxFiling)
class TaxFilingAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number', 'user', 'tax_type', 'fiscal_year',
        'calculated_tax', 'total_due', 'amount_paid', 'status', 'submission_date'
    ]
    list_filter = ['tax_type', 'status', 'fiscal_year', 'filing_period']
    search_fields = ['reference_number', 'user__email', 'user__tin']
    readonly_fields = ['id', 'reference_number', 'calculated_tax', 'taxable_income',
                       'total_due', 'created_at', 'updated_at']
    inlines = [TaxFilingDocumentInline]
    date_hierarchy = 'created_at'


@admin.register(TaxCalculationLog)
class TaxCalculationLogAdmin(admin.ModelAdmin):
    list_display = ['filing', 'calculated_at']
    readonly_fields = ['filing', 'calculation_details', 'calculated_at']
