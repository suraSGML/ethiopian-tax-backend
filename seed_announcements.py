"""Seed sample system announcements."""
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tax_system.settings.development'
import django
django.setup()

from django.utils import timezone
from datetime import timedelta
from tax_filing.models import SystemAnnouncement
from accounts.models import User

admin = User.objects.filter(role='super_admin').first()

announcements = [
    {
        'title': '📅 Annual Tax Filing Deadline — 31 March 2025',
        'message': 'The deadline for Annual Income Tax filings for fiscal year 2024 is 31 March 2025. Late submissions will incur a 5% penalty plus 2% monthly late fee. File now to avoid penalties.',
        'announcement_type': 'deadline',
        'target_role': 'taxpayer',
        'show_from': timezone.now(),
        'show_until': timezone.now() + timedelta(days=60),
    },
    {
        'title': '🔧 System Maintenance — Sunday 27 April 2025, 02:00–04:00 EAT',
        'message': 'The tax portal will be unavailable for scheduled maintenance. Please complete any pending submissions before this window.',
        'announcement_type': 'maintenance',
        'target_role': 'all',
        'show_from': timezone.now(),
        'show_until': timezone.now() + timedelta(days=3),
    },
    {
        'title': '✅ New Feature: Amendment Filing Now Available',
        'message': 'Taxpayers can now file amendments to correct errors in previously approved or paid filings. Navigate to any approved filing and click "Amend Filing".',
        'announcement_type': 'info',
        'target_role': 'taxpayer',
        'show_from': timezone.now(),
        'show_until': timezone.now() + timedelta(days=30),
    },
]

for ann_data in announcements:
    ann_data['created_by'] = admin
    obj, created = SystemAnnouncement.objects.get_or_create(
        title=ann_data['title'],
        defaults=ann_data
    )
    print(f"{'Created' if created else 'Exists'}: {obj.title[:60]}")

print("Done.")
