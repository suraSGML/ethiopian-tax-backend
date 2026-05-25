"""
Celery tasks for sending notifications.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id: str):
    try:
        from accounts.models import User
        from .models import Notification
        user = User.objects.get(id=user_id)
        subject = 'Welcome to Ethiopian Digital Tax System'
        message = f"""
Dear {user.get_full_name()},

Welcome to the Ethiopian Ministry of Revenue Digital Tax Payment System.

Your Tax Identification Number (TIN): {user.tin}

You can now:
- File your taxes online
- Make secure payments
- Track your filing history

For support, contact: support@mor.gov.et

Ministry of Revenue
Federal Democratic Republic of Ethiopia
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        Notification.objects.create(
            user=user,
            notification_type='general',
            channel='in_app',
            title='Welcome to the Tax System',
            message=f'Your TIN is {user.tin}. You can now file taxes and make payments.',
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_payment_confirmation(self, payment_id: str):
    try:
        from payments.models import Payment
        from .models import Notification
        payment = Payment.objects.select_related('user', 'tax_filing').get(id=payment_id)
        user = payment.user
        subject = f'Payment Confirmation - Receipt {payment.receipt_number}'
        message = f"""
Dear {user.get_full_name()},

Your tax payment has been processed successfully.

Receipt Number: {payment.receipt_number}
Transaction ID: {payment.transaction_id}
Amount: ETB {payment.amount:,.2f}
Filing Reference: {payment.tax_filing.reference_number}
Date: {payment.payment_date.strftime('%d %B %Y %H:%M') if payment.payment_date else 'N/A'}

Thank you for your compliance.

Ministry of Revenue
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        Notification.objects.create(
            user=user,
            notification_type='payment_confirmation',
            channel='in_app',
            title=f'Payment Confirmed - ETB {payment.amount:,.2f}',
            message=f'Receipt: {payment.receipt_number}. Transaction: {payment.transaction_id}',
            extra_data={'payment_id': str(payment.id), 'receipt': payment.receipt_number},
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_id: str, token: str):
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)
        reset_url = f'{settings.FRONTEND_URL if hasattr(settings, "FRONTEND_URL") else "http://localhost:3000"}/reset-password?token={token}'
        subject = 'Password Reset Request - Ethiopian Tax System'
        message = f"""
Dear {user.get_full_name()},

A password reset was requested for your account.

Click the link below to reset your password (valid for 2 hours):
{reset_url}

If you did not request this, please ignore this email.

Ministry of Revenue
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_email_verification(self, user_id: str, token: str):
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)
        verify_url = f'{settings.FRONTEND_URL if hasattr(settings, "FRONTEND_URL") else "http://localhost:3000"}/verify-email?token={token}'
        subject = 'Verify Your Email - Ethiopian Tax System'
        message = f"""
Dear {user.get_full_name()},

Thank you for registering with the Ethiopian Digital Tax Payment System.

Please verify your email address by clicking the link below (valid for 24 hours):
{verify_url}

Your Tax Identification Number (TIN): {user.tin}

If you did not register for this account, please ignore this email.

Ministry of Revenue
Federal Democratic Republic of Ethiopia
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_filing_status_notification(self, filing_id: str):
    try:
        from tax_filing.models import TaxFiling
        from .models import Notification
        filing = TaxFiling.objects.select_related('user').get(id=filing_id)
        user = filing.user
        status_map = {
            'approved': ('Filing Approved', 'Your tax filing has been approved. You can now proceed to payment.'),
            'rejected': ('Filing Rejected', f'Your filing was rejected. Notes: {filing.review_notes}'),
            'under_review': ('Filing Under Review', 'Your filing is currently under review by a tax officer.'),
        }
        title, msg = status_map.get(filing.status, ('Filing Update', f'Your filing status: {filing.status}'))
        Notification.objects.create(
            user=user,
            notification_type=f'filing_{filing.status}' if filing.status in ['approved', 'rejected'] else 'general',
            channel='in_app',
            title=title,
            message=msg,
            extra_data={'filing_id': str(filing.id), 'reference': filing.reference_number},
        )
        send_mail(title, msg, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def notify_officers_filing_submitted(self, filing_id: str):
    """Send notification to all tax officers when a filing is submitted."""
    try:
        from tax_filing.models import TaxFiling
        from accounts.models import User
        from .models import Notification
        filing = TaxFiling.objects.select_related('user').get(id=filing_id)
        
        # Get all tax officers
        officers = User.objects.filter(role__in=['tax_officer', 'super_admin'])
        
        for officer in officers:
            Notification.objects.create(
                user=officer,
                notification_type='filing_submitted',
                channel='in_app',
                title=f'New Filing Submitted - {filing.reference_number}',
                message=f'{filing.user.get_full_name()} submitted a {filing.get_tax_type_display()} filing for {filing.fiscal_year}. Total due: ETB {filing.total_due:,.2f}',
                extra_data={'filing_id': str(filing.id), 'reference': filing.reference_number, 'user_id': str(filing.user.id)},
            )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def send_deadline_reminders():
    """Periodic task: send reminders for upcoming filing deadlines."""
    from tax_filing.models import TaxFiling
    from .models import Notification
    from datetime import timedelta
    tomorrow = timezone.now().date() + timedelta(days=1)
    week_ahead = timezone.now().date() + timedelta(days=7)

    upcoming = TaxFiling.objects.filter(
        due_date__in=[tomorrow, week_ahead],
        status__in=['draft', 'submitted']
    ).select_related('user')

    for filing in upcoming:
        days_left = (filing.due_date - timezone.now().date()).days
        Notification.objects.create(
            user=filing.user,
            notification_type='filing_deadline',
            channel='in_app',
            title=f'Filing Deadline in {days_left} day(s)',
            message=f'Your {filing.get_tax_type_display()} filing (Ref: {filing.reference_number}) is due on {filing.due_date}.',
            extra_data={'filing_id': str(filing.id), 'due_date': str(filing.due_date)},
        )
