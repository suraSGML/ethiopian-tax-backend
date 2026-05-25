"""
Simulated Payment Gateway Integrations
In production, replace with real bank/mobile money APIs.
"""
import uuid
import random
from decimal import Decimal
from django.utils import timezone


class PaymentGatewayBase:
    def process_payment(self, amount: Decimal, reference: str, **kwargs) -> dict:
        raise NotImplementedError

    def check_status(self, transaction_id: str) -> dict:
        raise NotImplementedError

    def refund(self, transaction_id: str, amount: Decimal) -> dict:
        raise NotImplementedError


class CommercialBankGateway(PaymentGatewayBase):
    """Simulated Commercial Bank of Ethiopia gateway."""

    def process_payment(self, amount: Decimal, reference: str, **kwargs) -> dict:
        # Simulate 95% success rate
        success = random.random() > 0.05
        transaction_id = f'CBE-{uuid.uuid4().hex[:12].upper()}'
        if success:
            return {
                'success': True,
                'transaction_id': transaction_id,
                'amount': float(amount),
                'reference': reference,
                'timestamp': timezone.now().isoformat(),
                'bank': 'Commercial Bank of Ethiopia',
                'message': 'Payment processed successfully.',
            }
        return {
            'success': False,
            'error': 'Insufficient funds or bank connection error.',
            'reference': reference,
        }

    def check_status(self, transaction_id: str) -> dict:
        return {'transaction_id': transaction_id, 'status': 'completed'}

    def refund(self, transaction_id: str, amount: Decimal) -> dict:
        refund_id = f'REF-{uuid.uuid4().hex[:10].upper()}'
        return {
            'success': True,
            'refund_id': refund_id,
            'original_transaction': transaction_id,
            'refund_amount': float(amount),
            'timestamp': timezone.now().isoformat(),
        }


class TeleBirrGateway(PaymentGatewayBase):
    """Simulated TeleBirr (Ethio Telecom) mobile money gateway."""

    def process_payment(self, amount: Decimal, reference: str, phone_number: str = None, **kwargs) -> dict:
        success = random.random() > 0.08
        transaction_id = f'TLB-{uuid.uuid4().hex[:12].upper()}'
        if success:
            return {
                'success': True,
                'transaction_id': transaction_id,
                'amount': float(amount),
                'reference': reference,
                'phone': phone_number,
                'timestamp': timezone.now().isoformat(),
                'gateway': 'TeleBirr',
                'message': 'Mobile payment successful.',
            }
        return {
            'success': False,
            'error': 'Mobile money transaction failed. Check balance or phone number.',
        }

    def check_status(self, transaction_id: str) -> dict:
        return {'transaction_id': transaction_id, 'status': 'completed'}

    def refund(self, transaction_id: str, amount: Decimal) -> dict:
        return {
            'success': True,
            'refund_id': f'TLBREF-{uuid.uuid4().hex[:8].upper()}',
            'original_transaction': transaction_id,
            'refund_amount': float(amount),
        }


class AmoleGateway(PaymentGatewayBase):
    """Simulated Amole digital wallet gateway."""

    def process_payment(self, amount: Decimal, reference: str, **kwargs) -> dict:
        success = random.random() > 0.06
        transaction_id = f'AML-{uuid.uuid4().hex[:12].upper()}'
        if success:
            return {
                'success': True,
                'transaction_id': transaction_id,
                'amount': float(amount),
                'reference': reference,
                'timestamp': timezone.now().isoformat(),
                'gateway': 'Amole',
                'message': 'Amole payment successful.',
            }
        return {'success': False, 'error': 'Amole wallet transaction failed.'}

    def check_status(self, transaction_id: str) -> dict:
        return {'transaction_id': transaction_id, 'status': 'completed'}

    def refund(self, transaction_id: str, amount: Decimal) -> dict:
        return {
            'success': True,
            'refund_id': f'AMLREF-{uuid.uuid4().hex[:8].upper()}',
            'refund_amount': float(amount),
        }


GATEWAY_MAP = {
    'commercial_bank': CommercialBankGateway,
    'awash_bank': CommercialBankGateway,
    'dashen_bank': CommercialBankGateway,
    'bank_transfer': CommercialBankGateway,
    'telebirr': TeleBirrGateway,
    'mpesa': TeleBirrGateway,
    'amole': AmoleGateway,
    'cash': CommercialBankGateway,
}


def get_gateway(payment_method: str) -> PaymentGatewayBase:
    gateway_class = GATEWAY_MAP.get(payment_method, CommercialBankGateway)
    return gateway_class()
