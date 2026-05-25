import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        FILING_SUBMITTED = 'filing_submitted', 'Filing Submitted'
        FILING_DEADLINE = 'filing_deadline', 'Filing Deadline'
        PAYMENT_CONFIRMATION = 'payment_confirmation', 'Payment Confirmation'
        FILING_APPROVED = 'filing_approved', 'Filing Approved'
        FILING_REJECTED = 'filing_rejected', 'Filing Rejected'
        PENALTY_NOTICE = 'penalty_notice', 'Penalty Notice'
        GENERAL = 'general', 'General'
        SYSTEM = 'system', 'System'
        FRAUD_ALERT = 'fraud_alert', 'Fraud Alert'

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        IN_APP = 'in_app', 'In-App'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.IN_APP)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.notification_type} ({self.channel})'
