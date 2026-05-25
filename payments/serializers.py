from rest_framework import serializers
from .models import Payment, PaymentGatewayLog


class PaymentSerializer(serializers.ModelSerializer):
    filing_reference = serializers.CharField(source='tax_filing.reference_number', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = [
            'id', 'user', 'status', 'transaction_id', 'receipt_number',
            'payment_date', 'created_at', 'updated_at', 'is_refunded',
            'refund_amount', 'refund_date', 'filing_reference', 'user_name', 'user_tin'
        ]


class PaymentInitiateSerializer(serializers.Serializer):
    tax_filing_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=Payment.PaymentMethod.choices)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    bank_account = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value


class RefundSerializer(serializers.Serializer):
    refund_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    refund_reason = serializers.CharField()

    def validate_refund_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Refund amount must be greater than zero.')
        return value


class PaymentReceiptSerializer(serializers.ModelSerializer):
    filing_reference = serializers.CharField(source='tax_filing.reference_number', read_only=True)
    tax_type = serializers.CharField(source='tax_filing.tax_type', read_only=True)
    fiscal_year = serializers.IntegerField(source='tax_filing.fiscal_year', read_only=True)
    taxpayer_name = serializers.CharField(source='user.get_full_name', read_only=True)
    taxpayer_tin = serializers.CharField(source='user.tin', read_only=True)
    taxpayer_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'receipt_number', 'filing_reference', 'tax_type', 'fiscal_year',
            'taxpayer_name', 'taxpayer_tin', 'taxpayer_email',
            'amount', 'payment_method', 'status', 'transaction_id',
            'payment_date', 'created_at'
        ]
