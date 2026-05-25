from rest_framework import serializers
from django.utils import timezone
from .models import (
    TaxFiling, TaxFilingDocument, TaxCalculationLog,
    FilingStatusHistory, ComplianceCertificate, SystemAnnouncement,
    TaxAssessmentNotice, OfficialPaymentReceipt, TaxClearanceCertificate,
    WithholdingTaxCertificate, VATRefundApplication, TaxObjection, TaxTribunalCase
)
from .tax_calculator import (
    calculate_personal_income_tax, calculate_business_income_tax,
    calculate_vat, calculate_turnover_tax, calculate_penalty
)
from decimal import Decimal


class TaxFilingDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxFilingDocument
        fields = ['id', 'document_type', 'file', 'file_name', 'file_size', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at', 'file_name', 'file_size']

    def create(self, validated_data):
        file = validated_data.get('file')
        validated_data['file_name'] = file.name
        validated_data['file_size'] = file.size
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class TaxCalculationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxCalculationLog
        fields = ['calculation_details', 'calculated_at']


class FilingStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    changed_by_role = serializers.SerializerMethodField()

    class Meta:
        model = FilingStatusHistory
        fields = ['id', 'from_status', 'to_status', 'changed_by_name', 'changed_by_role', 'reason', 'timestamp']

    def get_changed_by_name(self, obj):
        return obj.changed_by.get_full_name() if obj.changed_by else 'System'

    def get_changed_by_role(self, obj):
        return obj.changed_by.role if obj.changed_by else 'system'


class TaxFilingSerializer(serializers.ModelSerializer):
    documents = TaxFilingDocumentSerializer(many=True, read_only=True)
    calculation_log = TaxCalculationLogSerializer(read_only=True)
    status_history = FilingStatusHistorySerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    balance_due = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    can_be_amended = serializers.BooleanField(read_only=True)
    can_be_appealed = serializers.BooleanField(read_only=True)
    days_until_appeal_expires = serializers.SerializerMethodField()

    class Meta:
        model = TaxFiling
        fields = '__all__'
        read_only_fields = [
            'id', 'user', 'calculated_tax', 'taxable_income', 'total_due',
            'penalty_amount', 'late_fee', 'amount_paid', 'reference_number',
            'submission_date', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'user_name', 'user_tin', 'user_email', 'balance_due',
            'can_be_amended', 'can_be_appealed', 'is_late_submission', 'days_late',
            'penalty_applied_at', 'appeal_date', 'appeal_resolved_at',
        ]

    def get_days_until_appeal_expires(self, obj):
        if obj.status != 'rejected' or not obj.reviewed_at:
            return None
        from datetime import timedelta
        expires = obj.reviewed_at + timedelta(days=30)
        remaining = (expires - timezone.now()).days
        return max(0, remaining)


class TaxFilingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxFiling
        fields = [
            'id', 'tax_type', 'filing_period', 'fiscal_year', 'period_month',
            'period_quarter', 'gross_income', 'allowable_deductions',
            'vat_collected', 'vat_paid', 'due_date', 'reference_number',
            'calculated_tax', 'taxable_income', 'total_due', 'status',
        ]
        read_only_fields = ['id', 'reference_number', 'calculated_tax', 'taxable_income', 'total_due', 'status']

    def validate(self, attrs):
        tax_type = attrs.get('tax_type')
        period = attrs.get('filing_period')
        month = attrs.get('period_month')
        quarter = attrs.get('period_quarter')

        # Convert empty strings to None for proper validation
        if month == '':
            month = None
        if quarter == '':
            quarter = None

        if period == TaxFiling.FilingPeriod.MONTHLY and not month:
            raise serializers.ValidationError({'period_month': 'Month is required for monthly filings.'})
        if period == TaxFiling.FilingPeriod.QUARTERLY and not quarter:
            raise serializers.ValidationError({'period_quarter': 'Quarter is required for quarterly filings.'})
        if month and not (1 <= month <= 12):
            raise serializers.ValidationError({'period_month': 'Month must be between 1 and 12.'})
        if quarter and not (1 <= quarter <= 4):
            raise serializers.ValidationError({'period_quarter': 'Quarter must be between 1 and 4.'})

        gross = attrs.get('gross_income', 0)
        if gross < 0:
            raise serializers.ValidationError({'gross_income': 'Gross income cannot be negative.'})

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        filing = TaxFiling(user=user, **validated_data)

        calc_result = self._calculate_tax(filing)
        filing.calculated_tax = Decimal(str(calc_result.get('calculated_tax', 0)))
        filing.taxable_income = Decimal(str(calc_result.get('taxable_income', filing.gross_income)))
        filing.total_due = filing.calculated_tax
        filing.save()

        TaxCalculationLog.objects.create(filing=filing, calculation_details=calc_result)

        # Record initial status
        from .workflow import record_status_change
        record_status_change(filing, '', 'draft', user, 'Filing created')

        return filing

    def _calculate_tax(self, filing):
        tax_type = filing.tax_type
        if tax_type == TaxFiling.TaxType.PERSONAL_INCOME:
            result = calculate_personal_income_tax(filing.gross_income)
            result['calculated_tax'] = result['annual_tax']
            result['taxable_income'] = result['gross_income']
            return result
        elif tax_type == TaxFiling.TaxType.BUSINESS_INCOME:
            return calculate_business_income_tax(filing.gross_income, filing.allowable_deductions)
        elif tax_type == TaxFiling.TaxType.VAT:
            result = calculate_vat(filing.vat_collected, filing.vat_paid)
            result['calculated_tax'] = result['net_vat_payable']
            result['taxable_income'] = result['taxable_sales']
            return result
        elif tax_type == TaxFiling.TaxType.TURNOVER:
            profile = getattr(filing.user, 'tax_profile', None)
            btype = profile.business_sector if profile else 'trade'
            result = calculate_turnover_tax(filing.gross_income, btype)
            result['taxable_income'] = result.get('annual_turnover', 0)
            return result
        return {'calculated_tax': 0, 'taxable_income': 0}


class TaxFilingReviewSerializer(serializers.ModelSerializer):
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = TaxFiling
        fields = ['status', 'review_notes', 'rejection_reason']


class TaxCalculationRequestSerializer(serializers.Serializer):
    tax_type = serializers.ChoiceField(choices=TaxFiling.TaxType.choices)
    gross_income = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
    allowable_deductions = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
    vat_collected = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
    vat_paid = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=0)
    business_type = serializers.ChoiceField(choices=['trade', 'service', 'manufacturing'], required=False, default='trade')
    days_overdue = serializers.IntegerField(required=False, default=0)


class ComplianceCertificateSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.get_full_name', read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceCertificate
        fields = '__all__'
        read_only_fields = ['id', 'certificate_number', 'issued_at']

    def get_is_expired(self, obj):
        from datetime import date
        return date.today() > obj.valid_until


class SystemAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemAnnouncement
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


# ─── Ethiopian Tax Workflow Serializers ─────────────────────────────────────────

class TaxAssessmentNoticeSerializer(serializers.ModelSerializer):
    filing_reference = serializers.CharField(source='filing.reference_number', read_only=True)
    assessed_by_name = serializers.CharField(source='assessed_by.get_full_name', read_only=True)
    assessed_by_tin = serializers.CharField(source='assessed_by.tin', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    can_be_objected = serializers.SerializerMethodField()

    class Meta:
        model = TaxAssessmentNotice
        fields = '__all__'
        read_only_fields = [
            'id', 'assessment_number', 'assessment_date', 'total_assessed',
            'assessed_by', 'created_at', 'updated_at'
        ]

    def get_days_until_expiry(self, obj):
        from datetime import date
        if obj.valid_until:
            return (obj.valid_until - date.today()).days
        return 0

    def get_can_be_objected(self, obj):
        from datetime import date
        return obj.status == 'pending' and obj.valid_until >= date.today()


class TaxAssessmentNoticeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxAssessmentNotice
        fields = [
            'filing', 'taxable_income', 'allowable_deductions', 'tax_assessed',
            'penalty_amount', 'late_fee', 'assessment_breakdown', 'assessment_notes'
        ]

    def create(self, validated_data):
        validated_data['assessed_by'] = self.context['request'].user
        return super().create(validated_data)


class OfficialPaymentReceiptSerializer(serializers.ModelSerializer):
    taxpayer_name = serializers.CharField(source='taxpayer.get_full_name', read_only=True)
    taxpayer_tin = serializers.CharField(source='taxpayer.tin', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.get_full_name', read_only=True)
    payment_reference_number = serializers.CharField(source='payment.reference_number', read_only=True)

    class Meta:
        model = OfficialPaymentReceipt
        fields = '__all__'
        read_only_fields = [
            'id', 'receipt_number', 'receipt_date', 'issued_by',
            'verification_code', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['issued_by'] = self.context['request'].user
        return super().create(validated_data)


class TaxClearanceCertificateSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.get_full_name', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = TaxClearanceCertificate
        fields = '__all__'
        read_only_fields = [
            'id', 'certificate_number', 'issued_date', 'expiry_date',
            'issued_by', 'verification_code', 'created_at', 'updated_at'
        ]

    def get_days_until_expiry(self, obj):
        from datetime import date
        if obj.expiry_date:
            return (obj.expiry_date - date.today()).days
        return 0

    def get_is_expired(self, obj):
        from datetime import date
        return obj.expiry_date < date.today()


class TaxClearanceCertificateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxClearanceCertificate
        fields = [
            'purpose', 'valid_for', 'purpose_description'
        ]

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        validated_data['issued_by'] = user
        
        # Calculate total tax paid and outstanding
        from .models import TaxFiling
        filings = TaxFiling.objects.filter(user=user, status='paid')
        total_paid = sum(f.amount_paid for f in filings)
        outstanding = sum(f.balance_due for f in filings.filter(status__in=['approved', 'overdue']))
        
        validated_data['total_tax_paid'] = total_paid
        validated_data['outstanding_amount'] = outstanding
        
        return super().create(validated_data)


class WithholdingTaxCertificateSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='withholding_agent.get_full_name', read_only=True)
    agent_tin = serializers.CharField(source='withholding_agent.tin', read_only=True)
    recipient_name_display = serializers.CharField(source='recipient_name', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.get_full_name', read_only=True)

    class Meta:
        model = WithholdingTaxCertificate
        fields = '__all__'
        read_only_fields = [
            'id', 'certificate_number', 'certificate_date', 'verification_code',
            'issued_by', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['withholding_agent'] = self.context['request'].user
        validated_data['issued_by'] = self.context['request'].user
        return super().create(validated_data)


class WithholdingTaxCertificateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithholdingTaxCertificate
        fields = [
            'recipient', 'recipient_tin', 'recipient_name', 'amount_withheld',
            'payment_date', 'payment_reference', 'gross_amount', 'withholding_rate',
            'purpose', 'purpose_description', 'tax_period', 'fiscal_year'
        ]

    def validate(self, attrs):
        if attrs['amount_withheld'] > attrs['gross_amount']:
            raise serializers.ValidationError('Amount withheld cannot exceed gross amount.')
        return attrs


class VATRefundApplicationSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.get_full_name', read_only=True)
    business_tin = serializers.CharField(source='business.tin', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)

    class Meta:
        model = VATRefundApplication
        fields = '__all__'
        read_only_fields = [
            'id', 'application_number', 'application_date', 'net_vat',
            'refund_amount', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['business'] = self.context['request'].user
        return super().create(validated_data)


class VATRefundApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VATRefundApplication
        fields = [
            'refund_period', 'period_month', 'period_quarter', 'fiscal_year',
            'input_vat', 'output_vat', 'bank_account', 'bank_name', 'account_name'
        ]

    def validate(self, attrs):
        if attrs['input_vat'] < attrs['output_vat']:
            raise serializers.ValidationError('Input VAT must be greater than output VAT for refund.')
        return attrs


class TaxObjectionSerializer(serializers.ModelSerializer):
    taxpayer_name = serializers.CharField(source='taxpayer.get_full_name', read_only=True)
    taxpayer_tin = serializers.CharField(source='taxpayer.tin', read_only=True)
    assessment_number = serializers.CharField(source='assessment.assessment_number', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = TaxObjection
        fields = '__all__'
        read_only_fields = [
            'id', 'objection_number', 'objection_date', 'created_at', 'updated_at'
        ]

    def get_days_until_expiry(self, obj):
        from datetime import date, timedelta
        if obj.objection_date:
            expiry = obj.objection_date + timedelta(days=30)
            return (expiry - date.today()).days
        return 0


class TaxObjectionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxObjection
        fields = [
            'assessment', 'objection_reason'
        ]

    def validate(self, attrs):
        assessment = attrs['assessment']
        if assessment.status != 'pending':
            raise serializers.ValidationError('Can only object to pending assessments.')
        return attrs

    def create(self, validated_data):
        validated_data['taxpayer'] = self.context['request'].user
        return super().create(validated_data)


class TaxObjectionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxObjection
        fields = ['status', 'review_notes', 'revised_assessment']


class TaxTribunalCaseSerializer(serializers.ModelSerializer):
    taxpayer_name = serializers.CharField(source='taxpayer.get_full_name', read_only=True)
    taxpayer_tin = serializers.CharField(source='taxpayer.tin', read_only=True)
    appeal_reference = serializers.CharField(source='appeal.reference_number', read_only=True)
    tribunal_officer_name = serializers.CharField(source='tribunal_officer.get_full_name', read_only=True)

    class Meta:
        model = TaxTribunalCase
        fields = '__all__'
        read_only_fields = [
            'id', 'case_number', 'filing_date', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['taxpayer'] = self.context['request'].user
        return super().create(validated_data)


class TaxTribunalCaseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxTribunalCase
        fields = ['appeal']

    def validate(self, attrs):
        appeal = attrs['appeal']
        if appeal.status != 'appealed':
            raise serializers.ValidationError('Can only file tribunal case for appealed filings.')
        return attrs
