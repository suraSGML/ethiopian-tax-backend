import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tax_system.settings.development'
import django
django.setup()

from django.db import connection
cursor = connection.cursor()

# Check tax_filings columns
cursor.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='tax_filings' ORDER BY column_name
""")
db_cols = set(r[0] for r in cursor.fetchall())
print("DB tax_filings columns:", sorted(db_cols))

# Check what model expects
from tax_filing.models import TaxFiling
model_cols = set(f.column for f in TaxFiling._meta.get_fields() if hasattr(f, 'column'))
print("\nModel expects:", sorted(model_cols))

missing = model_cols - db_cols
extra = db_cols - model_cols
print("\nMissing from DB (need migration):", sorted(missing))
print("Extra in DB (old fields):", sorted(extra))
