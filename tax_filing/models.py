import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.ethiopian_calendar import EthiopianCalendar
from .regional_tax_models import EthiopianRegion, IndustryTaxRule, TaxPayerProfile


class TaxFiling(models.Model):

    class TaxType(models.TextChoices):
        PERSONAL_INCOME = 'personal_income', 'Personal Income Tax'
        BUSINESS_INCOME = 'business_income', 'Business Income Tax'
        VAT = 'vat', 'Value Added Tax (VAT)'
        TURNOVER = 'turnover', 'Turnover Tax (TOT)'
        WITHHOLDING = 'withholding', 'Withholding Tax'

    class FilingStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        AMENDED = 'amended', 'Amended'
        APPEALED = 'appealed', 'Under Appeal'
        CANCELLED = 'cancelled', 'Cancelled'

    class FilingPeriod(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        ANNUAL = 'annual', 'Annual'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tax_filings'
    )
    tax_type = models.CharField(max_length=30, choices=TaxType.choices)
    filing_period = models.CharField(max_length=20, choices=FilingPeriod.choices)
    fiscal_year = models.IntegerField()  # Ethiopian fiscal year
    period_month = models.IntegerField(null=True, blank=True)
    period_quarter = models.IntegerField(null=True, blank=True)
    
    # Ethiopian calendar fields
    ethiopian_fiscal_year = models.IntegerField(null=True, blank=True, help_text='Ethiopian fiscal year')
    ethiopian_submission_date = models.DateField(null=True, blank=True, help_text='Submission date in Ethiopian calendar')

    gross_income = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    allowable_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    calculated_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    late_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=FilingStatus.choices, default=FilingStatus.DRAFT)
    submission_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_filings'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    is_amendment = models.BooleanField(default=False)
    original_filing = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='amendments'
    )
    amendment_reason = models.TextField(blank=True)

    appeal_reason = models.TextField(blank=True)
    appeal_date = models.DateTimeField(null=True, blank=True)
    appeal_resolved_at = models.DateTimeField(null=True, blank=True)
    appeal_outcome = models.CharField(max_length=20, blank=True)

    is_late_submission = models.BooleanField(default=False)
    days_late = models.IntegerField(default=0)
    penalty_applied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tax_filings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'tax_type', 'fiscal_year']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['reference_number']),
        ]

    def __str__(self):
        return f'{self.user.tin} - {self.tax_type} - {self.fiscal_year} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self._generate_reference()
        
        # Auto-calculate Ethiopian fiscal year if not set
        if not self.ethiopian_fiscal_year and self.fiscal_year:
            self.ethiopian_fiscal_year = self.fiscal_year
        
        super().save(*args, **kwargs)

    def _generate_reference(self):
        import random, string
        prefix = self.tax_type[:3].upper()
        rand = ''.join(random.choices(string.digits, k=6))
        return f'{prefix}-{self.fiscal_year}-{rand}'

    @property
    def balance_due(self):
        return max(self.total_due - self.amount_paid, Decimal('0'))

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.total_due and self.total_due > 0

    @property
    def can_be_amended(self):
        return self.status in [self.FilingStatus.PAID, self.FilingStatus.APPROVED]

    @property
    def can_be_appealed(self):
        if self.status != self.FilingStatus.REJECTED:
            return False
        from django.utils import timezone
        from datetime import timedelta
        if self.reviewed_at:
            return timezone.now() < self.reviewed_at + timedelta(days=30)
        return True


class TaxFilingDocument(models.Model):

    class DocumentType(models.TextChoices):
        INCOME_STATEMENT = 'income_statement', 'Income Statement'
        BALANCE_SHEET = 'balance_sheet', 'Balance Sheet'
        RECEIPT = 'receipt', 'Receipt'
        INVOICE = 'invoice', 'Invoice'
        BANK_STATEMENT = 'bank_statement', 'Bank Statement'
        APPEAL_LETTER = 'appeal_letter', 'Appeal Letter'
        AMENDMENT_SUPPORT = 'amendment_support', 'Amendment Supporting Doc'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filing = models.ForeignKey(TaxFiling, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to='tax_documents/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'tax_filing_documents'

    def __str__(self):
        return f'{self.filing.reference_number} - {self.document_type}'


class TaxCalculationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filing = models.OneToOneField(TaxFiling, on_delete=models.CASCADE, related_name='calculation_log')
    calculation_details = models.JSONField()
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tax_calculation_logs'


class FilingStatusHistory(models.Model):
    """Complete audit trail of every status change on a filing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filing = models.ForeignKey(TaxFiling, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'filing_status_history'
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.filing.reference_number}: {self.from_status} → {self.to_status}'


class ComplianceCertificate(models.Model):
    """Issued when a taxpayer has no outstanding obligations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='compliance_certificates'
    )
    certificate_number = models.CharField(max_length=30, unique=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='issued_certificates'
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField()
    is_valid = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)
    fiscal_year = models.IntegerField()

    class Meta:
        db_table = 'compliance_certificates'
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.certificate_number} - {self.user.tin}'

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=8))
            self.certificate_number = f'CC-{year}-{rand}'
        super().save(*args, **kwargs)


class SystemAnnouncement(models.Model):
    """System-wide announcements shown to all users."""

    class AnnouncementType(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Warning'
        MAINTENANCE = 'maintenance', 'Maintenance'
        DEADLINE = 'deadline', 'Deadline Reminder'
        URGENT = 'urgent', 'Urgent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    message = models.TextField()
    announcement_type = models.CharField(
        max_length=20, choices=AnnouncementType.choices, default=AnnouncementType.INFO
    )
    is_active = models.BooleanField(default=True)
    show_from = models.DateTimeField()
    show_until = models.DateTimeField(null=True, blank=True)
    target_role = models.CharField(
        max_length=20,
        choices=[('all', 'All Users'), ('taxpayer', 'Taxpayers Only'), ('tax_officer', 'Officers Only')],
        default='all'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_announcements'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.announcement_type}] {self.title}'


class TaxAssessmentNotice(models.Model):
    """Formal tax assessment document generated by tax officer."""
    
    class AssessmentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Acceptance'
        ACCEPTED = 'accepted', 'Accepted by Taxpayer'
        OBJECTED = 'objected', 'Objected by Taxpayer'
        EXPIRED = 'expired', 'Expired'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_number = models.CharField(max_length=30, unique=True)
    filing = models.ForeignKey(TaxFiling, on_delete=models.CASCADE, related_name='assessment_notices')
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assessments_made'
    )
    assessment_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField()
    
    # Assessment details
    taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allowable_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_assessed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    late_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_assessed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Assessment breakdown
    assessment_breakdown = models.JSONField(default=dict)
    assessment_notes = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=AssessmentStatus.choices, default=AssessmentStatus.PENDING)
    accepted_at = models.DateTimeField(null=True, blank=True)
    objected_at = models.DateTimeField(null=True, blank=True)
    objection_reason = models.TextField(blank=True)
    
    # Officer signature placeholder
    officer_signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tax_assessment_notices'
        ordering = ['-assessment_date']
        indexes = [
            models.Index(fields=['assessment_number']),
            models.Index(fields=['filing']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f'{self.assessment_number} - {self.filing.reference_number}'
    
    def save(self, *args, **kwargs):
        if not self.assessment_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.assessment_number = f'ASN-{year}-{rand}'
        
        # Calculate total assessed
        self.total_assessed = self.tax_assessed + self.penalty_amount + self.late_fee
        
        # Set valid until to 30 days from assessment date
        if not self.valid_until:
            from datetime import timedelta
            self.valid_until = self.assessment_date + timedelta(days=30)
        
        super().save(*args, **kwargs)


class OfficialPaymentReceipt(models.Model):
    """Official government payment receipt with ERCA seal."""
    
    class ReceiptStatus(models.TextChoices):
        ISSUED = 'issued', 'Issued'
        VERIFIED = 'verified', 'Verified'
        CANCELLED = 'cancelled', 'Cancelled'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=30, unique=True)
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, related_name='official_receipts')
    taxpayer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='official_receipts'
    )
    
    # Receipt details
    receipt_date = models.DateField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_reference = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100, blank=True)
    
    # Tax details
    tax_type = models.CharField(max_length=50)
    tax_period = models.CharField(max_length=50)
    fiscal_year = models.IntegerField()
    
    # Official details
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='receipts_issued'
    )
    issuing_office = models.CharField(max_length=200)
    officer_name = models.CharField(max_length=200)
    officer_signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    
    # Verification
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    verification_code = models.CharField(max_length=50, unique=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=ReceiptStatus.choices, default=ReceiptStatus.ISSUED)
    
    # Additional details
    receipt_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'official_payment_receipts'
        ordering = ['-receipt_date']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['payment']),
            models.Index(fields=['taxpayer']),
            models.Index(fields=['verification_code']),
        ]
    
    def __str__(self):
        return f'{self.receipt_number} - ETB {self.amount_paid}'
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=12))
            self.receipt_number = f'RCP-{year}-{rand}'
        
        if not self.verification_code:
            import secrets
            self.verification_code = secrets.token_urlsafe(32)
        
        super().save(*args, **kwargs)


class TaxClearanceCertificate(models.Model):
    """Tax clearance certificate for specific purposes (tenders, licenses, etc.)."""
    
    class CertificatePurpose(models.TextChoices):
        TENDER = 'tender', 'Government Tender'
        LICENSE = 'license', 'Business License'
        VISA = 'visa', 'Visa Application'
        LOAN = 'loan', 'Bank Loan'
        CONTRACT = 'contract', 'Government Contract'
        REGISTRATION = 'registration', 'Business Registration'
        OTHER = 'other', 'Other Purpose'
    
    class CertificateStatus(models.TextChoices):
        ISSUED = 'issued', 'Issued'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_number = models.CharField(max_length=30, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clearance_certificates'
    )
    
    # Purpose details
    purpose = models.CharField(max_length=30, choices=CertificatePurpose.choices)
    valid_for = models.CharField(max_length=200)  # Specific transaction/entity
    purpose_description = models.TextField(blank=True)
    
    # Certificate details
    issued_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clearances_issued'
    )
    
    # Financial details
    total_tax_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Verification
    verification_code = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=CertificateStatus.choices, default=CertificateStatus.ISSUED)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)
    
    # Supporting documents
    supporting_documents = models.ManyToManyField(TaxFilingDocument, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tax_clearance_certificates'
        ordering = ['-issued_date']
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['verification_code']),
        ]
    
    def __str__(self):
        return f'{self.certificate_number} - {self.user.tin} ({self.purpose})'
    
    def save(self, *args, **kwargs):
        if not self.certificate_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.certificate_number = f'TCC-{year}-{rand}'
        
        if not self.verification_code:
            import secrets
            self.verification_code = secrets.token_urlsafe(32)
        
        # Set expiry to 6 months from issue date
        if not self.expiry_date:
            from datetime import timedelta
            self.expiry_date = self.issued_date + timedelta(days=180)
        
        super().save(*args, **kwargs)


class WithholdingTaxCertificate(models.Model):
    """Withholding tax certificate for withheld amounts."""
    
    class WithholdingPurpose(models.TextChoices):
        SALARY = 'salary', 'Salary Withholding'
        CONTRACT = 'contract', 'Contract Payment'
        DIVIDEND = 'dividend', 'Dividend Payment'
        INTEREST = 'interest', 'Interest Payment'
        ROYALTY = 'royalty', 'Royalty Payment'
        RENT = 'rent', 'Rent Payment'
        OTHER = 'other', 'Other Withholding'
    
    class CertificateStatus(models.TextChoices):
        GENERATED = 'generated', 'Generated'
        ISSUED = 'issued', 'Issued'
        CANCELLED = 'cancelled', 'Cancelled'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_number = models.CharField(max_length=30, unique=True)
    
    # Parties
    withholding_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withholding_issued'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withholding_received'
    )
    recipient_tin = models.CharField(max_length=15)
    recipient_name = models.CharField(max_length=200)
    
    # Payment details
    amount_withheld = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    payment_reference = models.CharField(max_length=100)
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2)
    withholding_rate = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Purpose
    purpose = models.CharField(max_length=30, choices=WithholdingPurpose.choices)
    purpose_description = models.TextField(blank=True)
    
    # Certificate details
    certificate_date = models.DateField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withholding_certificates_issued'
    )
    officer_signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    
    # Verification
    verification_code = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=CertificateStatus.choices, default=CertificateStatus.GENERATED)
    issued_at = models.DateTimeField(null=True, blank=True)
    
    # Tax period
    tax_period = models.CharField(max_length=20)
    fiscal_year = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'withholding_tax_certificates'
        ordering = ['-certificate_date']
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['withholding_agent']),
            models.Index(fields=['recipient']),
            models.Index(fields=['verification_code']),
        ]
    
    def __str__(self):
        return f'{self.certificate_number} - ETB {self.amount_withheld}'
    
    def save(self, *args, **kwargs):
        if not self.certificate_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.certificate_number = f'WTC-{year}-{rand}'
        
        if not self.verification_code:
            import secrets
            self.verification_code = secrets.token_urlsafe(32)
        
        super().save(*args, **kwargs)


class VATRefundApplication(models.Model):
    """VAT refund application for businesses."""
    
    class RefundStatus(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class RefundPeriod(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        ANNUAL = 'annual', 'Annual'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=30, unique=True)
    business = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vat_refund_applications'
    )
    
    # Period
    refund_period = models.CharField(max_length=20, choices=RefundPeriod.choices)
    period_month = models.IntegerField(null=True, blank=True)
    period_quarter = models.IntegerField(null=True, blank=True)
    fiscal_year = models.IntegerField()
    
    # VAT details
    input_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    output_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    refund_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Application details
    application_date = models.DateField(auto_now_add=True)
    bank_account = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=200)
    
    # Supporting documents
    supporting_documents = models.ManyToManyField(TaxFilingDocument, blank=True)
    
    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='vat_refunds_reviewed'
    )
    review_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Payment
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.SUBMITTED)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vat_refund_applications'
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['application_number']),
            models.Index(fields=['business']),
            models.Index(fields=['status']),
            models.Index(fields=['fiscal_year']),
        ]
    
    def __str__(self):
        return f'{self.application_number} - ETB {self.refund_amount}'
    
    def save(self, *args, **kwargs):
        if not self.application_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.application_number = f'VRA-{year}-{rand}'
        
        # Calculate net VAT and refund amount
        self.net_vat = self.input_vat - self.output_vat
        if self.net_vat > 0:
            self.refund_amount = self.net_vat
        else:
            self.refund_amount = 0
        
        super().save(*args, **kwargs)


class TaxObjection(models.Model):
    """Tax objection to assessment (before appeal)."""
    
    class ObjectionStatus(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objection_number = models.CharField(max_length=30, unique=True)
    assessment = models.ForeignKey(TaxAssessmentNotice, on_delete=models.CASCADE, related_name='objections')
    taxpayer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tax_objections'
    )
    
    # Objection details
    objection_reason = models.TextField()
    objection_date = models.DateField(auto_now_add=True)
    supporting_documents = models.ManyToManyField(TaxFilingDocument, blank=True)
    
    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='objections_reviewed'
    )
    review_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Outcome
    status = models.CharField(max_length=20, choices=ObjectionStatus.choices, default=ObjectionStatus.SUBMITTED)
    outcome = models.CharField(max_length=20, blank=True)  # accepted, rejected
    revised_assessment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Withdrawal
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tax_objections'
        ordering = ['-objection_date']
        indexes = [
            models.Index(fields=['objection_number']),
            models.Index(fields=['assessment']),
            models.Index(fields=['taxpayer']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f'{self.objection_number} - {self.assessment.assessment_number}'
    
    def save(self, *args, **kwargs):
        if not self.objection_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.objection_number = f'OBJ-{year}-{rand}'
        super().save(*args, **kwargs)


class TaxTribunalCase(models.Model):
    """Tax tribunal case for escalated appeals."""
    
    class CaseStatus(models.TextChoices):
        FILED = 'filed', 'Filed'
        SCHEDULED = 'scheduled', 'Hearing Scheduled'
        IN_PROGRESS = 'in_progress', 'Hearing In Progress'
        DECIDED = 'decided', 'Decision Made'
        CLOSED = 'closed', 'Case Closed'
    
    class CaseOutcome(models.TextChoices):
        UPHELD = 'upheld', 'Appeal Upheld'
        DISMISSED = 'dismissed', 'Appeal Dismissed'
        MODIFIED = 'modified', 'Assessment Modified'
        SETTLED = 'settled', 'Settled'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_number = models.CharField(max_length=30, unique=True)
    appeal = models.ForeignKey(TaxFiling, on_delete=models.CASCADE, related_name='tribunal_cases')
    taxpayer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tribunal_cases'
    )
    
    # Case details
    filing_date = models.DateField(auto_now_add=True)
    hearing_date = models.DateField(null=True, blank=True)
    tribunal_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='tribunal_cases_presided'
    )
    
    # Decision
    decision = models.TextField(blank=True)
    decision_date = models.DateField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=CaseOutcome.choices, blank=True)
    revised_tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Supporting documents
    supporting_documents = models.ManyToManyField(TaxFilingDocument, blank=True)
    
    status = models.CharField(max_length=20, choices=CaseStatus.choices, default=CaseStatus.FILED)
    
    # Fees
    case_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fee_paid = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tax_tribunal_cases'
        ordering = ['-filing_date']
        indexes = [
            models.Index(fields=['case_number']),
            models.Index(fields=['appeal']),
            models.Index(fields=['taxpayer']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f'{self.case_number} - {self.appeal.reference_number}'
    
    def save(self, *args, **kwargs):
        if not self.case_number:
            import random, string
            from django.utils import timezone
            year = timezone.now().year
            rand = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.case_number = f'TTC-{year}-{rand}'
        super().save(*args, **kwargs)
