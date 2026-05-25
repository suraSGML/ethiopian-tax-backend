from rest_framework import serializers
from .models import AuditLog, FraudAlert


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ['id', 'timestamp']


class FraudAlertSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_tin = serializers.CharField(source='user.tin', read_only=True)

    class Meta:
        model = FraudAlert
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'user']


class FraudAlertResolveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
        ('investigating', 'Under Investigation'),
    ])
    resolution_notes = serializers.CharField(required=False, allow_blank=True)
