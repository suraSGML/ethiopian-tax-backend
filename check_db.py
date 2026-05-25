import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tax_system.settings.development'
import django
django.setup()

from accounts.models import User
from tax_filing.models import TaxFiling
from payments.models import Payment

print(f"\n{'='*55}")
print("  SUPABASE DATABASE STATUS")
print(f"{'='*55}")
print(f"  Users:    {User.objects.count()}")
print(f"  Filings:  {TaxFiling.objects.count()}")
print(f"  Payments: {Payment.objects.count()}")
print(f"{'='*55}")
print("\n  USERS:")
for u in User.objects.all().order_by('role'):
    print(f"  [{u.role:12}] {u.email:35} TIN:{u.tin}")

print("\n  FILINGS:")
for f in TaxFiling.objects.all():
    print(f"  {f.reference_number} | {f.tax_type:20} | {f.status:10} | ETB {f.total_due:,.2f}")

print("\n  PAYMENTS:")
for p in Payment.objects.all():
    print(f"  {p.receipt_number} | ETB {p.amount:,.2f} | {p.status}")
print()
