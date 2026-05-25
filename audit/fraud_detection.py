"""
Fraud Detection Rules Engine
Analyzes patterns and flags suspicious activity.
"""
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def check_fraud_patterns(user, filing=None, payment=None):
    """Run all fraud detection rules and create alerts if needed."""
    alerts = []
    alerts.extend(_check_rapid_filings(user))
    alerts.extend(_check_unusual_amounts(user, filing))
    alerts.extend(_check_duplicate_filing(user, filing))
    if payment:
        alerts.extend(_check_large_refund(payment))
    return alerts


def _check_rapid_filings(user):
    """Flag if user submits more than 5 filings in 24 hours."""
    from tax_filing.models import TaxFiling
    from .models import FraudAlert
    alerts = []
    cutoff = timezone.now() - timedelta(hours=24)
    recent_count = TaxFiling.objects.filter(user=user, created_at__gte=cutoff).count()
    if recent_count > 5:
        alert = FraudAlert.objects.create(
            user=user,
            alert_type=FraudAlert.AlertType.RAPID_FILINGS,
            description=f'User submitted {recent_count} filings in the last 24 hours.',
            severity='high',
            extra_data={'filing_count': recent_count, 'window_hours': 24},
        )
        alerts.append(alert)
    return alerts


def _check_unusual_amounts(user, filing):
    """Flag if filing amount is 10x higher than user's average."""
    from tax_filing.models import TaxFiling
    from .models import FraudAlert
    alerts = []
    if not filing:
        return alerts
    avg = TaxFiling.objects.filter(
        user=user, tax_type=filing.tax_type
    ).exclude(id=filing.id).aggregate(
        avg=__import__('django.db.models', fromlist=['Avg']).Avg('calculated_tax')
    )['avg']
    if avg and filing.calculated_tax > avg * 10:
        alert = FraudAlert.objects.create(
            user=user,
            alert_type=FraudAlert.AlertType.UNUSUAL_FILING_AMOUNT,
            description=f'Filing amount {filing.calculated_tax} ETB is significantly higher than average {avg:.2f} ETB.',
            severity='medium',
            extra_data={
                'filing_id': str(filing.id),
                'amount': float(filing.calculated_tax),
                'average': float(avg),
            },
        )
        alerts.append(alert)
    return alerts


def _check_duplicate_filing(user, filing):
    """Flag if a filing for the same period already exists."""
    from tax_filing.models import TaxFiling
    from .models import FraudAlert
    alerts = []
    if not filing:
        return alerts
    duplicate_qs = TaxFiling.objects.filter(
        user=user,
        tax_type=filing.tax_type,
        fiscal_year=filing.fiscal_year,
        filing_period=filing.filing_period,
    ).exclude(id=filing.id).exclude(status=TaxFiling.FilingStatus.REJECTED)

    if filing.period_month:
        duplicate_qs = duplicate_qs.filter(period_month=filing.period_month)
    if filing.period_quarter:
        duplicate_qs = duplicate_qs.filter(period_quarter=filing.period_quarter)

    if duplicate_qs.exists():
        alert = FraudAlert.objects.create(
            user=user,
            alert_type=FraudAlert.AlertType.DUPLICATE_FILING,
            description=f'Duplicate filing detected for {filing.tax_type} {filing.fiscal_year}.',
            severity='high',
            extra_data={'filing_id': str(filing.id)},
        )
        alerts.append(alert)
    return alerts


def _check_large_refund(payment):
    """Flag refunds over 50,000 ETB."""
    from .models import FraudAlert
    alerts = []
    LARGE_REFUND_THRESHOLD = Decimal('50000')
    if payment.refund_amount and payment.refund_amount > LARGE_REFUND_THRESHOLD:
        alert = FraudAlert.objects.create(
            user=payment.user,
            alert_type=FraudAlert.AlertType.LARGE_REFUND,
            description=f'Large refund of {payment.refund_amount} ETB requested.',
            severity='critical',
            extra_data={'payment_id': str(payment.id), 'refund_amount': float(payment.refund_amount)},
        )
        alerts.append(alert)
    return alerts
