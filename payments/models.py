import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal


class Payment(models.Model):

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        COMMERCIAL_BANK = 'commercial_bank', 'Commercial Bank of Ethiopia'
        AWASH_BANK = 'awash_bank', 'Awash Bank'
        DASHEN_BANK = 'dashen_bank', 'Dashen Bank'
        TELEBIRR = 'telebirr', 'TeleBirr (Ethio Telecom)'
        MPESA = 'mpesa', 'M-Pesa'
        AMOLE = 'amole', 'Amole'
        CASH = 'cash', 'Cash at Tax Office'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
        CANCELLED = 'cancelled', 'Cancelled'
        DISPUTED = 'disputed', 'Disputed'
        STUCK = 'stuck', 'Stuck / Needs Review'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tax_filing = models.ForeignKey(
        'tax_filing.TaxFiling', on_delete=models.CASCADE, related_name='payments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    external_reference = models.CharField(max_length=100, null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Refund
    is_refunded = models.BooleanField(default=False)
    refund_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    refund_date = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True)
    refund_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_refunds'
    )

    # Dispute
    dispute_reason = models.TextField(blank=True)
    dispute_date = models.DateTimeField(null=True, blank=True)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)
    dispute_outcome = models.CharField(max_length=20, blank=True)

    # Manual resolution (for stuck payments)
    manually_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_payments'
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['receipt_number']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Payment {self.receipt_number or self.id} - {self.amount} ETB ({self.status})'

    def save(self, *args, **kwargs):
        if not self.receipt_number and self.status == self.PaymentStatus.COMPLETED:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)

    def _generate_receipt_number(self):
        import random, string
        from django.utils import timezone
        year = timezone.now().year
        rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=8))
        return f'RCP-{year}-{rand}'

    @property
    def is_stuck(self):
        if self.status != self.PaymentStatus.PROCESSING:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=30)


class PaymentGatewayLog(models.Model):
    """Logs all interactions with payment gateways for audit purposes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='gateway_logs')
    gateway = models.CharField(max_length=50)
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    status_code = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_gateway_logs'
