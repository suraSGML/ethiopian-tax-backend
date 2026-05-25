from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count

from .models import AuditLog, FraudAlert
from .serializers import AuditLogSerializer, FraudAlertSerializer, FraudAlertResolveSerializer
from accounts.permissions import IsTaxOfficer, IsSuperAdmin


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user', 'reviewed_by').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsTaxOfficer]
    filterset_fields = ['action', 'is_suspicious', 'reviewed', 'method']
    search_fields = ['user__email', 'user__tin', 'ip_address', 'description']
    ordering_fields = ['timestamp', 'action']

    @action(detail=False, methods=['get'])
    def suspicious(self, request):
        qs = self.get_queryset().filter(is_suspicious=True, reviewed=False)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_reviewed(self, request, pk=None):
        log = self.get_object()
        log.reviewed = True
        log.reviewed_by = request.user
        log.save()
        return Response({'message': 'Marked as reviewed.'})

    @action(detail=False, methods=['get'])
    def activity_summary(self, request):
        from datetime import timedelta
        last_30 = timezone.now() - timedelta(days=30)
        qs = AuditLog.objects.filter(timestamp__gte=last_30)
        data = {
            'total_actions': qs.count(),
            'suspicious_count': qs.filter(is_suspicious=True).count(),
            'by_action': list(qs.values('action').annotate(count=Count('id')).order_by('-count')[:10]),
            'unique_users': qs.values('user').distinct().count(),
        }
        return Response(data)


class FraudAlertViewSet(viewsets.ModelViewSet):
    queryset = FraudAlert.objects.select_related('user', 'resolved_by').all()
    serializer_class = FraudAlertSerializer
    permission_classes = [IsTaxOfficer]
    filterset_fields = ['alert_type', 'severity', 'status']
    search_fields = ['user__email', 'user__tin', 'description']
    ordering_fields = ['created_at', 'severity']
    http_method_names = ['get', 'patch', 'head', 'options']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        serializer = FraudAlertResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert.status = serializer.validated_data['status']
        alert.resolution_notes = serializer.validated_data.get('resolution_notes', '')
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.save()
        return Response({'message': f'Alert {alert.status}.', 'alert_id': str(alert.id)})

    @action(detail=False, methods=['get'])
    def open_alerts(self, request):
        qs = self.get_queryset().filter(status=FraudAlert.AlertStatus.OPEN)
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})
