from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from accounts.permissions import IsTaxOfficer


class TaxpayerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        from tax_filing.models import TaxFiling
        from payments.models import Payment
        from notifications.models import Notification

        filings = TaxFiling.objects.filter(user=user)
        payments = Payment.objects.filter(user=user, status='completed')

        # Current year
        current_year = timezone.now().year

        data = {
            'user': {
                'name': user.get_full_name(),
                'tin': user.tin,
                'email': user.email,
                'role': user.role,
                'is_verified': user.is_verified,
            },
            'filings': {
                'total': filings.count(),
                'draft': filings.filter(status='draft').count(),
                'submitted': filings.filter(status='submitted').count(),
                'approved': filings.filter(status='approved').count(),
                'paid': filings.filter(status='paid').count(),
                'overdue': filings.filter(status='overdue').count(),
                'current_year': filings.filter(fiscal_year=current_year).count(),
            },
            'payments': {
                'total_paid': payments.aggregate(total=Sum('amount'))['total'] or 0,
                'transaction_count': payments.count(),
                'recent': list(
                    payments.order_by('-payment_date').values(
                        'receipt_number', 'amount', 'payment_method', 'payment_date'
                    )[:5]
                ),
            },
            'tax_due': {
                'total_due': filings.filter(
                    status__in=['approved', 'overdue']
                ).aggregate(total=Sum('total_due'))['total'] or 0,
                'total_balance': filings.aggregate(
                    balance=Sum('total_due') - Sum('amount_paid')
                )['balance'] or 0,
            },
            'upcoming_deadlines': list(
                filings.filter(
                    due_date__gte=timezone.now().date(),
                    due_date__lte=timezone.now().date() + timedelta(days=30),
                    status__in=['draft', 'submitted', 'approved']
                ).values('reference_number', 'tax_type', 'due_date', 'total_due')[:5]
            ),
            'notifications': {
                'unread_count': Notification.objects.filter(user=user, is_read=False).count(),
            },
        }
        return Response(data)


class AdminDashboardView(APIView):
    permission_classes = [IsTaxOfficer]

    def get(self, request):
        from tax_filing.models import TaxFiling
        from payments.models import Payment
        from accounts.models import User
        from audit.models import FraudAlert

        now = timezone.now()
        current_year = now.year
        last_30 = now - timedelta(days=30)

        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_revenue = Payment.objects.filter(
            status='completed', payment_date__gte=last_30
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_taxpayers = User.objects.filter(role='taxpayer').count()
        active_taxpayers = User.objects.filter(role='taxpayer', is_active=True).count()

        total_filings = TaxFiling.objects.count()
        paid_filings = TaxFiling.objects.filter(status='paid').count()
        compliance_rate = round((paid_filings / total_filings * 100), 2) if total_filings > 0 else 0

        data = {
            'revenue': {
                'total': float(total_revenue),
                'last_30_days': float(monthly_revenue),
                'by_tax_type': list(
                    TaxFiling.objects.filter(status='paid').values('tax_type').annotate(
                        total=Sum('amount_paid'), count=Count('id')
                    )
                ),
            },
            'taxpayers': {
                'total': total_taxpayers,
                'active': active_taxpayers,
                'new_this_month': User.objects.filter(
                    role='taxpayer', date_joined__gte=last_30
                ).count(),
                'verified': User.objects.filter(role='taxpayer', is_verified=True).count(),
            },
            'filings': {
                'total': total_filings,
                'pending_review': TaxFiling.objects.filter(status='submitted').count(),
                'overdue': TaxFiling.objects.filter(status='overdue').count(),
                'compliance_rate': compliance_rate,
                'by_status': {
                    s: TaxFiling.objects.filter(status=s).count()
                    for s, _ in TaxFiling.FilingStatus.choices
                },
            },
            'fraud_alerts': {
                'open': FraudAlert.objects.filter(status='open').count(),
                'critical': FraudAlert.objects.filter(status='open', severity='critical').count(),
                'recent': list(
                    FraudAlert.objects.filter(status='open').order_by('-created_at').values(
                        'alert_type', 'severity', 'created_at', 'user__email'
                    )[:5]
                ),
            },
            'recent_payments': list(
                Payment.objects.filter(status='completed').order_by('-payment_date').values(
                    'receipt_number', 'amount', 'payment_method', 'payment_date', 'user__tin'
                )[:10]
            ),
        }
        return Response(data)


class RevenueReportView(APIView):
    permission_classes = [IsTaxOfficer]

    def get(self, request):
        from payments.models import Payment
        from tax_filing.models import TaxFiling

        year = request.query_params.get('year', timezone.now().year)
        monthly_data = []
        for month in range(1, 13):
            revenue = Payment.objects.filter(
                status='completed',
                payment_date__year=year,
                payment_date__month=month,
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_data.append({'month': month, 'revenue': float(revenue)})

        return Response({
            'year': year,
            'monthly_revenue': monthly_data,
            'total_annual': sum(m['revenue'] for m in monthly_data),
            'by_tax_type': list(
                TaxFiling.objects.filter(
                    fiscal_year=year, status='paid'
                ).values('tax_type').annotate(
                    total=Sum('amount_paid'), count=Count('id')
                )
            ),
        })
