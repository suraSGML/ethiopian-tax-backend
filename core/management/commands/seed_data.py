"""
Management command to seed the database with sample data for testing.
Usage: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Seed the database with sample Ethiopian tax system data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')
        self._create_users()
        self._create_filings()
        self._create_payments()
        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))

    def _create_users(self):
        from accounts.models import User, TaxProfile
        from accounts.utils import generate_tin

        # Super Admin
        if not User.objects.filter(email='admin@mor.gov.et').exists():
            admin = User.objects.create_superuser(
                email='admin@mor.gov.et',
                password='Admin@1234',
                first_name='System',
                last_name='Administrator',
            )
            self.stdout.write(f'  Created super admin: {admin.email}')

        # Tax Officer
        if not User.objects.filter(email='officer@mor.gov.et').exists():
            officer = User.objects.create_user(
                email='officer@mor.gov.et',
                password='Officer@1234',
                first_name='Abebe',
                last_name='Kebede',
                role=User.Role.TAX_OFFICER,
                is_verified=True,
            )
            self.stdout.write(f'  Created tax officer: {officer.email}')

        # Sample taxpayers
        taxpayers = [
            ('Tigist', 'Haile', 'tigist@example.com', 'individual', 'Addis Ababa'),
            ('Dawit', 'Bekele', 'dawit@example.com', 'business', 'Dire Dawa'),
            ('Sara', 'Tesfaye', 'sara@example.com', 'individual', 'Bahir Dar'),
            ('Yonas', 'Girma', 'yonas@example.com', 'business', 'Hawassa'),
            ('Meron', 'Alemu', 'meron@example.com', 'individual', 'Mekelle'),
        ]

        for first, last, email, tp_type, city in taxpayers:
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    email=email,
                    password='Taxpayer@1234',
                    first_name=first,
                    last_name=last,
                    role=User.Role.TAXPAYER,
                    is_verified=True,
                )
                user.tin = generate_tin()
                user.save()
                TaxProfile.objects.create(
                    user=user,
                    taxpayer_type=tp_type,
                    address=f'{random.randint(100, 999)} Main Street',
                    city=city,
                    region='Addis Ababa' if city == 'Addis Ababa' else city,
                    business_name=f'{first} {last} Trading' if tp_type == 'business' else None,
                    business_sector='trade' if tp_type == 'business' else None,
                    is_vat_registered=tp_type == 'business',
                )
                self.stdout.write(f'  Created taxpayer: {email} (TIN: {user.tin})')

    def _create_filings(self):
        from accounts.models import User
        from tax_filing.models import TaxFiling, TaxCalculationLog
        from tax_filing.tax_calculator import (
            calculate_personal_income_tax, calculate_business_income_tax
        )
        from datetime import date

        taxpayers = User.objects.filter(role='taxpayer')
        for user in taxpayers:
            profile = getattr(user, 'tax_profile', None)
            if not profile:
                continue

            if profile.taxpayer_type == 'individual':
                income = Decimal(str(random.randint(3000, 15000)))
                result = calculate_personal_income_tax(income)
                filing = TaxFiling.objects.create(
                    user=user,
                    tax_type='personal_income',
                    filing_period='annual',
                    fiscal_year=2024,
                    gross_income=income * 12,
                    taxable_income=income * 12,
                    calculated_tax=Decimal(str(result['annual_tax'])),
                    total_due=Decimal(str(result['annual_tax'])),
                    status=random.choice(['approved', 'paid', 'submitted']),
                    due_date=date(2025, 3, 31),
                )
                TaxCalculationLog.objects.get_or_create(
                    filing=filing,
                    defaults={'calculation_details': result}
                )
            else:
                gross = Decimal(str(random.randint(500000, 5000000)))
                deductions = gross * Decimal('0.3')
                result = calculate_business_income_tax(gross, deductions)
                filing = TaxFiling.objects.create(
                    user=user,
                    tax_type='business_income',
                    filing_period='annual',
                    fiscal_year=2024,
                    gross_income=gross,
                    allowable_deductions=deductions,
                    taxable_income=Decimal(str(result['taxable_income'])),
                    calculated_tax=Decimal(str(result['calculated_tax'])),
                    total_due=Decimal(str(result['calculated_tax'])),
                    status=random.choice(['approved', 'paid', 'submitted']),
                    due_date=date(2025, 3, 31),
                )
                TaxCalculationLog.objects.get_or_create(
                    filing=filing,
                    defaults={'calculation_details': result}
                )
            self.stdout.write(f'  Created filing for {user.email}: {filing.reference_number}')

    def _create_payments(self):
        from tax_filing.models import TaxFiling
        from payments.models import Payment
        import uuid

        paid_filings = TaxFiling.objects.filter(status='paid')
        for filing in paid_filings:
            if not Payment.objects.filter(tax_filing=filing).exists():
                payment = Payment.objects.create(
                    tax_filing=filing,
                    user=filing.user,
                    amount=filing.total_due,
                    payment_method=random.choice(['commercial_bank', 'telebirr', 'amole']),
                    status='completed',
                    transaction_id=f'TXN-{uuid.uuid4().hex[:12].upper()}',
                    payment_date=timezone.now(),
                )
                filing.amount_paid = filing.total_due
                filing.save()
                self.stdout.write(f'  Created payment: {payment.receipt_number}')
