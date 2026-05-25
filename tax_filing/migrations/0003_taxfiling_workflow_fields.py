"""
Migration: Add workflow fields to TaxFiling
- Amendment tracking (is_amendment, original_filing, amendment_reason)
- Appeal tracking (appeal_reason, appeal_date, appeal_resolved_at, appeal_outcome)
- Compliance fields (is_late_submission, days_late, penalty_applied_at)
- Rejection reason (rejection_reason)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tax_filing', '0002_compliancecertificate_filingstatushistory_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Amendment fields
        migrations.AddField(
            model_name='taxfiling',
            name='is_amendment',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='original_filing',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='amendments',
                to='tax_filing.taxfiling',
            ),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='amendment_reason',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        # Appeal fields
        migrations.AddField(
            model_name='taxfiling',
            name='appeal_reason',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='appeal_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='appeal_resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='appeal_outcome',
            field=models.CharField(blank=True, default='', max_length=20),
            preserve_default=False,
        ),
        # Compliance fields
        migrations.AddField(
            model_name='taxfiling',
            name='is_late_submission',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='days_late',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='taxfiling',
            name='penalty_applied_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Rejection reason
        migrations.AddField(
            model_name='taxfiling',
            name='rejection_reason',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        # New statuses (CharField max_length already 20, just update choices)
        migrations.AlterField(
            model_name='taxfiling',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('submitted', 'Submitted'),
                    ('under_review', 'Under Review'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                    ('paid', 'Paid'),
                    ('overdue', 'Overdue'),
                    ('amended', 'Amended'),
                    ('appealed', 'Under Appeal'),
                    ('cancelled', 'Cancelled'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
