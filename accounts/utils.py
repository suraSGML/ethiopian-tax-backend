import random
import string
import secrets
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse


def generate_tin():
    """Generate a unique Ethiopian Tax Identification Number (TIN)."""
    from .models import User
    while True:
        # Format: ET + 9 digits
        tin = 'ET' + ''.join(random.choices(string.digits, k=9))
        if not User.objects.filter(tin=tin).exists():
            return tin


def generate_reset_token():
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(48)


def lockout_response(request, credentials, *args, **kwargs):
    """Custom response for locked out users."""
    return JsonResponse(
        {
            'error': 'Account temporarily locked due to too many failed login attempts. '
                     'Please try again in 30 minutes or contact support.'
        },
        status=403
    )


def get_token_expiry():
    return timezone.now() + timedelta(hours=2)
