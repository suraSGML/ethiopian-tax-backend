from django.core.management.base import BaseCommand
from tax_filing.models import TaxFiling


class Command(BaseCommand):
    help = 'Generate reference numbers for existing filings that do not have one'

    def handle(self, *args, **options):
        filings_without_ref = TaxFiling.objects.filter(reference_number__isnull=True) | TaxFiling.objects.filter(reference_number='')
        count = filings_without_ref.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('All filings already have reference numbers.'))
            return
        
        self.stdout.write(f'Found {count} filings without reference numbers. Generating...')
        
        for filing in filings_without_ref:
            filing.reference_number = filing._generate_reference()
            filing.save(update_fields=['reference_number'])
            self.stdout.write(f'Generated reference: {filing.reference_number} for filing {filing.id}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated reference numbers for {count} filings.'))
