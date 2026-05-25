from django.contrib import admin
from .models import AuditLog, FraudAlert


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'ip_address', 'status_code', 'is_suspicious', 'timestamp']
    list_filter = ['action', 'is_suspicious', 'reviewed', 'method']
    search_fields = ['user__email', 'ip_address', 'description']
    readonly_fields = list(f.name for f in AuditLog._meta.fields)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_type', 'severity', 'status', 'created_at']
    list_filter = ['alert_type', 'severity', 'status']
    search_fields = ['user__email', 'user__tin', 'description']
    readonly_fields = ['id', 'created_at']
