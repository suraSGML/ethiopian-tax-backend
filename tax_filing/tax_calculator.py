"""
Ethiopian Tax Calculation Engine
Implements Ethiopian Ministry of Revenue tax rules.
"""
from decimal import Decimal
from django.conf import settings
from .ethiopian_tax_rules import EthiopianTaxCalculator, EthiopianTurnoverTax, EthiopianPenalties


TAX_CONFIG = settings.ETHIOPIAN_TAX


def calculate_personal_income_tax(monthly_income: Decimal, num_dependents: int = 0) -> dict:
    """
    Calculate Ethiopian personal income tax using progressive brackets.
    Now uses EthiopianTaxCalculator for accurate Ethiopian tax rules.
    """
    income = Decimal(str(monthly_income))
    annual_income = income * 12
    
    # Use Ethiopian tax calculator
    result = EthiopianTaxCalculator.calculate_personal_income_tax(
        gross_income=annual_income,
        allowable_deductions=Decimal('0'),
        num_dependents=num_dependents
    )
    
    monthly_tax = result['tax_amount'] / 12
    
    return {
        'gross_income': float(income),
        'annual_income': float(annual_income),
        'tax_rate': float(result['effective_rate']),
        'personal_deductions': float(result['personal_deductions']),
        'taxable_income': float(result['taxable_income']),
        'monthly_tax': float(monthly_tax),
        'annual_tax': float(result['tax_amount']),
        'effective_rate': float(result['effective_rate']),
    }


def calculate_business_income_tax(gross_income: Decimal, allowable_deductions: Decimal, 
                              business_type: str = 'private_limited_company', 
                              industry: str = None) -> dict:
    """
    Calculate business income tax using Ethiopian tax rules.
    Now uses EthiopianTaxCalculator for accurate Ethiopian tax rules.
    """
    gross = Decimal(str(gross_income))
    deductions = Decimal(str(allowable_deductions))
    
    # Use Ethiopian tax calculator
    result = EthiopianTaxCalculator.calculate_business_tax(
        gross_income=gross,
        allowable_deductions=deductions,
        business_type=business_type,
        industry=industry
    )

    return {
        'gross_income': float(gross),
        'allowable_deductions': float(deductions),
        'taxable_income': float(result['taxable_income']),
        'tax_rate': float(result['tax_rate']),
        'calculated_tax': float(result['tax_amount']),
        'effective_rate': float(result['tax_amount'] / gross * 100) if gross > 0 else 0,
        'business_type': business_type,
        'industry': industry,
    }


def calculate_vat(taxable_sales: Decimal, vat_paid_on_purchases: Decimal, item_type: str = 'standard') -> dict:
    """
    Calculate VAT using Ethiopian VAT rules.
    Now uses EthiopianTaxCalculator for accurate Ethiopian tax rules.
    """
    sales = Decimal(str(taxable_sales))
    purchases = Decimal(str(vat_paid_on_purchases))
    
    # Use Ethiopian tax calculator
    result = EthiopianTaxCalculator.calculate_vat(
        sales_amount=sales,
        purchases_amount=purchases,
        item_type=item_type
    )

    return {
        'taxable_sales': float(sales),
        'purchases_amount': float(purchases),
        'vat_rate': float(result['vat_rate']),
        'output_vat': float(result['output_vat']),
        'input_vat': float(result['input_vat']),
        'net_vat_payable': float(result['net_vat']),
        'item_type': item_type,
    }


def calculate_turnover_tax(annual_turnover: Decimal, business_type: str = 'trade') -> dict:
    """
    Calculate Turnover Tax using Ethiopian TOT rules.
    Now uses EthiopianTaxCalculator for accurate Ethiopian tax rules.
    """
    turnover = Decimal(str(annual_turnover))
    
    # Use Ethiopian tax calculator
    tax = EthiopianTurnoverTax.calculate_tot(turnover)
    
    if turnover > EthiopianTurnoverTax.EXEMPTION_THRESHOLD:
        return {
            'error': 'Business exceeds TOT threshold. Must register for VAT.',
            'vat_threshold': float(EthiopianTurnoverTax.EXEMPTION_THRESHOLD),
            'annual_turnover': float(turnover),
        }

    return {
        'annual_turnover': float(turnover),
        'business_type': business_type,
        'tax_rate': f'{EthiopianTurnoverTax.RATE}%',
        'calculated_tax': float(tax),
        'vat_threshold': float(EthiopianTurnoverTax.EXEMPTION_THRESHOLD),
    }


def calculate_penalty(tax_amount: Decimal, days_overdue: int) -> dict:
    """
    Calculate penalty and late fees for overdue tax payments using Ethiopian rules.
    Now uses EthiopianPenalties for accurate Ethiopian penalty calculations.
    """
    tax = Decimal(str(tax_amount))
    
    # Use Ethiopian penalty calculator
    penalty = EthiopianPenalties.calculate_late_filing_penalty(tax, days_overdue)
    late_fee = EthiopianPenalties.calculate_late_payment_interest(tax, days_overdue)
    total_penalty = penalty + late_fee

    return {
        'original_tax': float(tax),
        'days_overdue': days_overdue,
        'penalty_amount': float(penalty),
        'late_fee': float(late_fee),
        'total_penalty': float(total_penalty),
        'total_due': float(tax + total_penalty),
    }


def calculate_withholding_tax(payment_amount: Decimal, payment_type: str) -> dict:
    """
    Calculate withholding tax using Ethiopian withholding tax rules.
    Now uses EthiopianWithholdingTax for accurate Ethiopian withholding tax calculations.
    """
    from .ethiopian_tax_rules import EthiopianWithholdingTax
    
    amount = Decimal(str(payment_amount))
    tax = EthiopianWithholdingTax.calculate_withholding_tax(amount, payment_type)
    rate = EthiopianWithholdingTax.RATES.get(payment_type, 0.0)

    return {
        'payment_amount': float(amount),
        'payment_type': payment_type,
        'withholding_rate': float(rate),
        'withholding_tax': float(tax),
        'net_payment': float(amount - tax),
    }
