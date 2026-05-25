from django.contrib import admin
from .models import Payment, PaymentGatewayLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'user', 'amount', 'payment_method', 'status', 'payment_date', 'is_refunded']
    list_filter = ['status', 'payment_method', 'is_refunded']
    search_fields = ['receipt_number', 'transaction_id', 'user__email', 'user__tin']
    readonly_fields = ['id', 'receipt_number', 'transaction_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(PaymentGatewayLog)
class PaymentGatewayLogAdmin(admin.ModelAdmin):
    list_display = ['payment', 'gateway', 'status_code', 'created_at']
    readonly_fields = ['payment', 'gateway', 'request_data', 'response_data', 'status_code', 'created_at']
