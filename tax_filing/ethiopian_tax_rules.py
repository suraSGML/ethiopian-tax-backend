"""
Ethiopian Tax Rules and Calculations
Based on Ethiopian Revenue Authority (ERA) tax regulations
"""

from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional


class EthiopianTaxBrackets:
    """Ethiopian Personal Income Tax Brackets (2024/2025)"""
    
    # Monthly income tax brackets (ETB)
    MONTHLY_BRACKETS = [
        (0, 600, 0),           # 0-600: 0%
        (601, 1650, 10),       # 601-1650: 10%
        (1651, 3200, 15),      # 1651-3200: 15%
        (3201, 5250, 20),      # 3201-5250: 20%
        (5251, 7800, 25),      # 5251-7800: 25%
        (7801, 10920, 30),     # 7801-10920: 30%
        (10921, float('inf'), 35),  # Above 10920: 35%
    ]
    
    # Annual income tax brackets (ETB)
    ANNUAL_BRACKETS = [
        (0, 7200, 0),          # 0-7200: 0%
        (7201, 19800, 10),      # 7201-19800: 10%
        (19801, 38400, 15),     # 19801-38400: 15%
        (38401, 63000, 20),     # 38401-63000: 20%
        (63001, 93600, 25),     # 63001-93600: 25%
        (93601, 131040, 30),    # 93601-131040: 30%
        (131041, float('inf'), 35),  # Above 131040: 35%
    ]
    
    @classmethod
    def calculate_personal_income_tax(cls, annual_income: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculate personal income tax based on annual income
        Returns: (tax_amount, effective_rate)
        """
        income = float(annual_income)
        total_tax = 0.0
        
        for min_income, max_income, rate in cls.ANNUAL_BRACKETS:
            if income > min_income:
                taxable_amount = min(income, max_income) - min_income
                bracket_tax = taxable_amount * (rate / 100)
                total_tax += bracket_tax
                if income <= max_income:
                    break
        
        tax_amount = Decimal(str(round(total_tax, 2)))
        effective_rate = (tax_amount / annual_income * 100) if annual_income > 0 else Decimal('0')
        
        return tax_amount, effective_rate


class EthiopianVATRates:
    """Ethiopian Value Added Tax Rates"""
    
    STANDARD_RATE = 15.0  # 15% standard VAT
    ZERO_RATED = 0.0      # 0% for exports
    EXEMPT = 0.0         # Exempt goods/services
    
    # Zero-rated goods/services
    ZERO_RATED_ITEMS = [
        'export_goods',
        'export_services',
        'international_transport',
        'diplomatic_goods',
    ]
    
    # Exempt goods/services
    EXEMPT_ITEMS = [
        'basic_food_items',
        'medical_services',
        'educational_services',
        'agricultural_inputs',
        'books',
        'newspapers',
    ]
    
    @classmethod
    def get_vat_rate(cls, item_type: str) -> float:
        """Get VAT rate based on item type"""
        if item_type in cls.ZERO_RATED_ITEMS:
            return cls.ZERO_RATED
        elif item_type in cls.EXEMPT_ITEMS:
            return cls.EXEMPT
        return cls.STANDARD_RATE
    
    @classmethod
    def calculate_vat(cls, amount: Decimal, item_type: str = 'standard') -> Decimal:
        """Calculate VAT amount"""
        rate = cls.get_vat_rate(item_type)
        return Decimal(str(float(amount) * (rate / 100)))


class EthiopianTurnoverTax:
    """Ethiopian Turnover Tax (TOT)"""
    
    RATE = 2.0  # 2% turnover tax
    EXEMPTION_THRESHOLD = 500000  # ETB 500,000 annual turnover
    
    @classmethod
    def calculate_tot(cls, turnover: Decimal) -> Decimal:
        """Calculate turnover tax"""
        if turnover <= cls.EXEMPTION_THRESHOLD:
            return Decimal('0')
        return Decimal(str(float(turnover) * (cls.RATE / 100)))


class EthiopianWithholdingTax:
    """Ethiopian Withholding Tax Rates"""
    
    # Withholding tax rates by payment type
    RATES = {
        'salary': 0.0,  # Progressive income tax applies
        'contract': 2.0,  # 2% for government contracts
        'dividend': 0.0,  # 0% for dividends (may change)
        'interest': 5.0,  # 5% for interest income
        'royalty': 10.0,  # 10% for royalties
        'rent': 0.0,  # 0% for rent (may change)
        'consultancy': 2.0,  # 2% for consultancy services
        'transport': 2.0,  # 2% for transport services
    }
    
    @classmethod
    def calculate_withholding_tax(cls, amount: Decimal, payment_type: str) -> Decimal:
        """Calculate withholding tax"""
        rate = cls.RATES.get(payment_type, 0.0)
        return Decimal(str(float(amount) * (rate / 100)))


class EthiopianBusinessTax:
    """Ethiopian Business Income Tax"""
    
    # Business tax rates by business type
    RATES = {
        'sole_proprietorship': 35.0,  # Progressive up to 35%
        'partnership': 35.0,
        'private_limited_company': 30.0,
        'public_limited_company': 30.0,
        'cooperative': 30.0,
        'ngo': 0.0,  # Exempt
        'government': 0.0,  # Exempt
    }
    
    # Industry-specific rates
    INDUSTRY_RATES = {
        'manufacturing': 25.0,
        'agriculture': 0.0,  # Exempt
        'tourism': 25.0,
        'technology': 25.0,
        'export': 0.0,  # Exempt
        'mining': 30.0,
        'construction': 30.0,
        'trade': 30.0,
        'services': 30.0,
    }
    
    @classmethod
    def get_business_tax_rate(cls, business_type: str, industry: Optional[str] = None) -> float:
        """Get business tax rate"""
        if industry and industry in cls.INDUSTRY_RATES:
            return cls.INDUSTRY_RATES[industry]
        return cls.RATES.get(business_type, 30.0)
    
    @classmethod
    def calculate_business_tax(cls, taxable_income: Decimal, business_type: str, 
                              industry: Optional[str] = None) -> Decimal:
        """Calculate business income tax"""
        rate = cls.get_business_tax_rate(business_type, industry)
        return Decimal(str(float(taxable_income) * (rate / 100)))


class EthiopianTaxDeductions:
    """Ethiopian Tax Deductions and Allowances"""
    
    # Standard deductions
    PERSONAL_ALLOWANCE = Decimal('3600')  # ETB 3,600 per year
    DEPENDENT_ALLOWANCE = Decimal('600')  # ETB 600 per dependent per year
    MAX_DEPENDENTS = 4  # Maximum number of dependents
    
    # Business deductions
    BUSINESS_DEDUCTIONS = [
        'operating_expenses',
        'salaries_wages',
        'rent',
        'utilities',
        'depreciation',
        'interest_expenses',
        'bad_debts',
        'insurance',
        'maintenance',
    ]
    
    # Non-deductible expenses
    NON_DEDUCTIBLE = [
        'personal_expenses',
        'fines_penalties',
        'political_contributions',
        'entertainment_excess',
    ]
    
    @classmethod
    def calculate_personal_deductions(cls, num_dependents: int = 0) -> Decimal:
        """Calculate personal tax deductions"""
        dependents = min(num_dependents, cls.MAX_DEPENDENTS)
        return cls.PERSONAL_ALLOWANCE + (cls.DEPENDENT_ALLOWANCE * dependents)


class EthiopianTaxDeadlines:
    """Ethiopian Tax Filing Deadlines"""
    
    # Monthly filing deadlines
    MONTHLY_DEADLINE = 30  # 30th of following month
    
    # Quarterly filing deadlines
    QUARTERLY_DEADLINES = {
        1: 30,  # April 30 for Q1
        2: 31,  # July 31 for Q2
        3: 31,  # October 31 for Q3
        4: 31,  # January 31 for Q4
    }
    
    # Annual filing deadline
    ANNUAL_DEADLINE_MONTH = 7  # July
    ANNUAL_DEADLINE_DAY = 31   # July 31
    
    # VAT filing deadline
    VAT_DEADLINE = 30  # 30th of following month
    
    @classmethod
    def get_filing_deadline(cls, filing_period: str, period_value: int, fiscal_year: int) -> date:
        """Calculate filing deadline based on period"""
        if filing_period == 'monthly':
            # Deadline is 30th of following month
            if period_value == 12:
                deadline_month = 1
                deadline_year = fiscal_year + 1
            else:
                deadline_month = period_value + 1
                deadline_year = fiscal_year
            return date(deadline_year, deadline_month, cls.MONTHLY_DEADLINE)
        
        elif filing_period == 'quarterly':
            deadline_day = cls.QUARTERLY_DEADLINES.get(period_value, 30)
            if period_value == 4:
                deadline_month = 1
                deadline_year = fiscal_year + 1
            else:
                deadline_month = period_value * 3 + 1
                deadline_year = fiscal_year
            return date(deadline_year, deadline_month, deadline_day)
        
        elif filing_period == 'annual':
            return date(fiscal_year + 1, cls.ANNUAL_DEADLINE_MONTH, cls.ANNUAL_DEADLINE_DAY)
        
        return date(fiscal_year + 1, 12, 31)


class EthiopianPenalties:
    """Ethiopian Tax Penalties and Interest"""
    
    LATE_FILING_PENALTY_RATE = 0.05  # 5% of tax due
    LATE_PAYMENT_INTEREST_RATE = 0.02  # 2% per month
    MAX_PENALTY_CAP = 0.25  # 25% of tax due maximum
    
    @classmethod
    def calculate_late_filing_penalty(cls, tax_due: Decimal, days_late: int) -> Decimal:
        """Calculate late filing penalty"""
        if days_late <= 0:
            return Decimal('0')
        
        penalty = Decimal(str(float(tax_due) * cls.LATE_FILING_PENALTY_RATE))
        max_penalty = Decimal(str(float(tax_due) * cls.MAX_PENALTY_CAP))
        return min(penalty, max_penalty)
    
    @classmethod
    def calculate_late_payment_interest(cls, tax_due: Decimal, days_late: int) -> Decimal:
        """Calculate late payment interest"""
        if days_late <= 0:
            return Decimal('0')
        
        months_late = days_late / 30
        interest = Decimal(str(float(tax_due) * cls.LATE_PAYMENT_INTEREST_RATE * months_late))
        return interest


class EthiopianTaxCalculator:
    """Main Ethiopian Tax Calculator"""
    
    @staticmethod
    def calculate_personal_income_tax(
        gross_income: Decimal,
        allowable_deductions: Decimal,
        num_dependents: int = 0
    ) -> Dict:
        """Calculate personal income tax with all deductions"""
        
        # Calculate personal allowances
        personal_deductions = EthiopianTaxDeductions.calculate_personal_deductions(num_dependents)
        total_deductions = allowable_deductions + personal_deductions
        
        # Calculate taxable income
        taxable_income = max(gross_income - total_deductions, Decimal('0'))
        
        # Calculate tax
        tax_amount, effective_rate = EthiopianTaxBrackets.calculate_personal_income_tax(taxable_income)
        
        return {
            'gross_income': gross_income,
            'allowable_deductions': allowable_deductions,
            'personal_deductions': personal_deductions,
            'total_deductions': total_deductions,
            'taxable_income': taxable_income,
            'tax_amount': tax_amount,
            'effective_rate': effective_rate,
        }
    
    @staticmethod
    def calculate_vat(
        sales_amount: Decimal,
        purchases_amount: Decimal,
        item_type: str = 'standard'
    ) -> Dict:
        """Calculate VAT payable"""
        
        output_vat = EthiopianVATRates.calculate_vat(sales_amount, item_type)
        input_vat = EthiopianVATRates.calculate_vat(purchases_amount, item_type)
        net_vat = output_vat - input_vat
        
        return {
            'sales_amount': sales_amount,
            'purchases_amount': purchases_amount,
            'output_vat': output_vat,
            'input_vat': input_vat,
            'net_vat': max(net_vat, Decimal('0')),
            'vat_rate': EthiopianVATRates.STANDARD_RATE,
        }
    
    @staticmethod
    def calculate_business_tax(
        gross_income: Decimal,
        allowable_deductions: Decimal,
        business_type: str,
        industry: Optional[str] = None
    ) -> Dict:
        """Calculate business income tax"""
        
        taxable_income = max(gross_income - allowable_deductions, Decimal('0'))
        tax_amount = EthiopianBusinessTax.calculate_business_tax(taxable_income, business_type, industry)
        tax_rate = EthiopianBusinessTax.get_business_tax_rate(business_type, industry)
        
        return {
            'gross_income': gross_income,
            'allowable_deductions': allowable_deductions,
            'taxable_income': taxable_income,
            'tax_amount': tax_amount,
            'tax_rate': tax_rate,
            'business_type': business_type,
            'industry': industry,
        }
