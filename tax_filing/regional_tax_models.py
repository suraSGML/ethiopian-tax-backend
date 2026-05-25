"""
Ethiopian Regional Tax Variations
Different regions may have different tax rates and rules
"""

from django.db import models
from django.conf import settings
import uuid


class EthiopianRegion(models.Model):
    """Ethiopian administrative regions"""
    
    class RegionType(models.TextChoices):
        CITY_ADMINISTRATION = 'city_administration', 'City Administration'
        REGIONAL_STATE = 'regional_state', 'Regional State'
        CHARTERED_CITY = 'chartered_city', 'Chartered City'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)
    name_amharic = models.CharField(max_length=100)
    name_english = models.CharField(max_length=100)
    region_type = models.CharField(max_length=30, choices=RegionType.choices)
    capital_city = models.CharField(max_length=100, blank=True)
    
    # Tax variation flags
    has_custom_vat_rate = models.BooleanField(default=False)
    has_custom_turnover_rate = models.BooleanField(default=False)
    has_custom_income_tax = models.BooleanField(default=False)
    
    # Custom rates (if applicable)
    custom_vat_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    custom_turnover_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    custom_income_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Additional regional tax
    has_regional_tax = models.BooleanField(default=False)
    regional_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    regional_tax_name_amharic = models.CharField(max_length=100, blank=True)
    regional_tax_name_english = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ethiopian_regions'
        ordering = ['name_english']
    
    def __str__(self):
        return f'{self.name_english} ({self.code})'


class RegionalTaxExemption(models.Model):
    """Tax exemptions specific to regions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.ForeignKey(EthiopianRegion, on_delete=models.CASCADE, related_name='exemptions')
    
    exemption_type = models.CharField(max_length=50)  # vat, income_tax, turnover, etc.
    exemption_name_amharic = models.CharField(max_length=200)
    exemption_name_english = models.CharField(max_length=200)
    description_amharic = models.TextField(blank=True)
    description_english = models.TextField(blank=True)
    
    # Conditions
    min_income_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_income_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    industry_specific = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'regional_tax_exemptions'
        ordering = ['-valid_from']
    
    def __str__(self):
        return f'{self.region.name_english} - {self.exemption_name_english}'


class RegionalTaxDeadline(models.Model):
    """Custom tax deadlines for regions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.ForeignKey(EthiopianRegion, on_delete=models.CASCADE, related_name='deadlines')
    
    tax_type = models.CharField(max_length=50)  # vat, income_tax, turnover, etc.
    filing_period = models.CharField(max_length=20)  # monthly, quarterly, annual
    
    # Custom deadline
    deadline_day = models.IntegerField(help_text='Day of month (1-31)')
    deadline_month_offset = models.IntegerField(default=1, help_text='Months after period end')
    
    # Ethiopian calendar deadline
    ethiopian_deadline_day = models.IntegerField(null=True, blank=True)
    ethiopian_deadline_month = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    fiscal_year = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'regional_tax_deadlines'
        ordering = ['fiscal_year', 'tax_type']
    
    def __str__(self):
        return f'{self.region.name_english} - {self.tax_type} - FY {self.fiscal_year}'


class IndustryTaxRule(models.Model):
    """Industry-specific tax rules"""
    
    class IndustryCategory(models.TextChoices):
        AGRICULTURE = 'agriculture', 'Agriculture'
        MANUFACTURING = 'manufacturing', 'Manufacturing'
        MINING = 'mining', 'Mining'
        CONSTRUCTION = 'construction', 'Construction'
        TRADE = 'trade', 'Trade'
        SERVICES = 'services', 'Services'
        TOURISM = 'tourism', 'Tourism'
        TECHNOLOGY = 'technology', 'Technology'
        FINANCE = 'finance', 'Finance'
        TRANSPORT = 'transport', 'Transport'
        EDUCATION = 'education', 'Education'
        HEALTH = 'health', 'Health'
        MEDIA = 'media', 'Media'
        OTHER = 'other', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    industry_code = models.CharField(max_length=20, unique=True)
    industry_category = models.CharField(max_length=50, choices=IndustryCategory.choices)
    industry_name_amharic = models.CharField(max_length=200)
    industry_name_english = models.CharField(max_length=200)
    description_amharic = models.TextField(blank=True)
    description_english = models.TextField(blank=True)
    
    # Tax rates
    income_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    turnover_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Special provisions
    is_exempt_from_vat = models.BooleanField(default=False)
    is_exempt_from_turnover = models.BooleanField(default=False)
    has_reduced_rate = models.BooleanField(default=False)
    reduced_rate_amount = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Thresholds
    vat_registration_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    turnover_tax_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Allowable deductions (JSON field for flexibility)
    allowable_deductions = models.JSONField(default=list, blank=True)
    
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'industry_tax_rules'
        ordering = ['industry_category', 'industry_name_english']
    
    def __str__(self):
        return f'{self.industry_name_english} ({self.industry_code})'


class TaxPayerProfile(models.Model):
    """Extended profile for Ethiopian taxpayers"""
    
    class BusinessType(models.TextChoices):
        SOLE_PROPRIETORSHIP = 'sole_proprietorship', 'Sole Proprietorship'
        PARTNERSHIP = 'partnership', 'Partnership'
        PRIVATE_LIMITED = 'private_limited', 'Private Limited Company'
        PUBLIC_LIMITED = 'public_limited', 'Public Limited Company'
        COOPERATIVE = 'cooperative', 'Cooperative'
        NGO = 'ngo', 'NGO'
        GOVERNMENT = 'government', 'Government Entity'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='taxpayer_profile'
    )
    
    # Business information
    business_name_amharic = models.CharField(max_length=200, blank=True)
    business_name_english = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=50, choices=BusinessType.choices, blank=True)
    industry = models.ForeignKey(IndustryTaxRule, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Location
    region = models.ForeignKey(EthiopianRegion, on_delete=models.SET_NULL, null=True, blank=True)
    city_amharic = models.CharField(max_length=100, blank=True)
    city_english = models.CharField(max_length=100, blank=True)
    sub_city_amharic = models.CharField(max_length=100, blank=True)
    sub_city_english = models.CharField(max_length=100, blank=True)
    woreda_amharic = models.CharField(max_length=100, blank=True)
    woreda_english = models.CharField(max_length=100, blank=True)
    house_number = models.CharField(max_length=50, blank=True)
    
    # Registration details
    trade_license_number = models.CharField(max_length=50, blank=True)
    trade_license_issue_date = models.DateField(null=True, blank=True)
    trade_license_expiry_date = models.DateField(null=True, blank=True)
    
    # Tax registration
    vat_registered = models.BooleanField(default=False)
    vat_registration_date = models.DateField(null=True, blank=True)
    vat_registration_number = models.CharField(max_length=50, blank=True)
    
    turnover_tax_registered = models.BooleanField(default=False)
    turnover_tax_registration_date = models.DateField(null=True, blank=True)
    
    # Employment information (for personal income tax)
    employer_name = models.CharField(max_length=200, blank=True)
    employer_tin = models.CharField(max_length=20, blank=True)
    employment_type = models.CharField(max_length=50, blank=True)  # permanent, contract, etc.
    
    # Dependents (for personal tax deductions)
    number_of_dependents = models.IntegerField(default=0)
    dependent_details = models.JSONField(default=dict, blank=True)
    
    # Additional information
    preferred_language = models.CharField(
        max_length=5,
        choices=[('en', 'English'), ('am', 'Amharic')],
        default='en'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'taxpayer_profiles'
    
    def __str__(self):
        return f'{self.user.email} - {self.business_name_english or "Individual"}'
