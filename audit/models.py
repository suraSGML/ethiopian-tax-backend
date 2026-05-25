import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    class ActionType(models.TextChoices):
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        REGISTER = 'register', 'Register'
        PROFILE_UPDATE = 'profile_update', 'Profile Update'
        PASSWORD_CHANGE = 'password_change', 'Password Change'
        FILING_CREATE = 'filing_create', 'Filing Created'
        FILING_SUBMIT = 'filing_submit', 'Filing Submitted'
        FILING_UPDATE = 'filing_update', 'Filing Updated'
        FILING_REVIEW = 'filing_review', 'Filing Reviewed'
        PAYMENT_INITIATE = 'payment_initiate', 'Payment Initiated'
        PAYMENT_COMPLETE = 'payment_complete', 'Payment Completed'
        PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
        REFUND = 'refund', 'Refund Processed'
        USER_DEACTIVATE = 'user_deactivate', 'User Deactivated'
        USER_ACTIVATE = 'user_activate', 'User Activated'
        DOCUMENT_UPLOAD = 'document_upload', 'Document Uploaded'
        ADMIN_ACTION = 'admin_action', 'Admin Action'
        SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
        DATA_EXPORT = 'data_export', 'Data Exported'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_suspicious = models.BooleanField(default=False)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_audit_logs'
    )

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else 'Anonymous'
        return f'{user_str} - {self.action} at {self.timestamp}'


class FraudAlert(models.Model):
    class AlertType(models.TextChoices):
        MULTIPLE_FAILED_LOGINS = 'multiple_failed_logins', 'Multiple Failed Logins'
        UNUSUAL_FILING_AMOUNT = 'unusual_filing_amount', 'Unusual Filing Amount'
        RAPID_FILINGS = 'rapid_filings', 'Rapid Multiple Filings'
        DUPLICATE_FILING = 'duplicate_filing', 'Duplicate Filing Detected'
        SUSPICIOUS_IP = 'suspicious_ip', 'Suspicious IP Activity'
        LARGE_REFUND = 'large_refund', 'Large Refund Request'
        INCONSISTENT_DATA = 'inconsistent_data', 'Inconsistent Financial Data'

    class AlertStatus(models.TextChoices):
        OPEN = 'open', 'Open'
        INVESTIGATING = 'investigating', 'Under Investigation'
        RESOLVED = 'resolved', 'Resolved'
        FALSE_POSITIVE = 'false_positive', 'False Positive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fraud_alerts'
    )
    alert_type = models.CharField(max_length=40, choices=AlertType.choices)
    description = models.TextField()
    severity = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium'
    )
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.OPEN)
    related_audit_log = models.ForeignKey(AuditLog, on_delete=models.SET_NULL, null=True, blank=True)
    extra_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_alerts'
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'fraud_alerts'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.alert_type} - {self.user.email} ({self.severity})'
