"""Mark migration 0003 as applied since columns already exist."""
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tax_system.settings.development'
import django
django.setup()

from django.db import connection

# Check if 0003 is already recorded
cursor = connection.cursor()
cursor.execute(
    "SELECT id FROM django_migrations WHERE app='tax_filing' AND name='0003_taxfiling_workflow_fields'"
)
exists = cursor.fetchone()

if exists:
    print("Migration 0003 already recorded as applied.")
else:
    cursor.execute(
        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
        ['tax_filing', '0003_taxfiling_workflow_fields']
    )
    print("Migration 0003 marked as applied.")

# Also check payments 0002
cursor.execute(
    "SELECT id FROM django_migrations WHERE app='payments' AND name='0002_payment_dispute_date_payment_dispute_outcome_and_more'"
)
exists2 = cursor.fetchone()
if exists2:
    print("Payments 0002 already recorded.")
else:
    cursor.execute(
        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
        ['payments', '0002_payment_dispute_date_payment_dispute_outcome_and_more']
    )
    print("Payments 0002 marked as applied.")

print("Done.")
