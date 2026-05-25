from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Sum, Count
from decimal import Decimal

from .models import Payment, PaymentGatewayLog
from .serializers import (
    PaymentSerializer, PaymentInitiateSerializer,
    RefundSerializer, PaymentReceiptSerializer
)
from .gateway import get_gateway
from tax_filing.models import TaxFiling
from accounts.permissions import IsTaxOfficer
from notifications.tasks import send_payment_confirmation


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['receipt_number', 'transaction_id', 'user__tin']
    ordering_fields = ['created_at', 'amount', 'payment_date']

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related('tax_filing', 'user')
        if user.is_taxpayer:
            return qs.filter(user=user)
        return qs

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.PaymentStatus.COMPLETED:
            return Response({'error': 'Receipt only available for completed payments.'}, status=400)
        serializer = PaymentReceiptSerializer(payment)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def receipt_pdf(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.PaymentStatus.COMPLETED:
            return Response({'error': 'Receipt only available for completed payments.'}, status=400)
        from .receipt import generate_pdf_receipt, REPORTLAB_AVAILABLE
        content = generate_pdf_receipt(payment)
        content_type = 'application/pdf' if REPORTLAB_AVAILABLE else 'text/plain'
        ext = 'pdf' if REPORTLAB_AVAILABLE else 'txt'
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number}.{ext}"'
        return response

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def refund(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.PaymentStatus.COMPLETED:
            return Response({'error': 'Only completed payments can be refunded.'}, status=400)
        if payment.is_refunded:
            return Response({'error': 'Payment already refunded.'}, status=400)

        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund_amount = serializer.validated_data['refund_amount']

        if refund_amount > payment.amount:
            return Response({'error': 'Refund amount exceeds payment amount.'}, status=400)

        gateway = get_gateway(payment.payment_method)
        result = gateway.refund(payment.transaction_id, refund_amount)

        if result.get('success'):
            payment.is_refunded = True
            payment.refund_amount = refund_amount
            payment.refund_date = timezone.now()
            payment.refund_reason = serializer.validated_data['refund_reason']
            payment.status = Payment.PaymentStatus.REFUNDED
            payment.save()

            # Update filing amount paid
            filing = payment.tax_filing
            filing.amount_paid = max(filing.amount_paid - refund_amount, Decimal('0'))
            filing.save()

            return Response({'message': 'Refund processed successfully.', 'refund_id': result.get('refund_id')})
        return Response({'error': 'Refund failed.', 'details': result}, status=400)

    @action(detail=False, methods=['get'], permission_classes=[IsTaxOfficer])
    def revenue_summary(self, request):
        qs = Payment.objects.filter(status=Payment.PaymentStatus.COMPLETED)
        data = {
            'total_revenue': qs.aggregate(total=Sum('amount'))['total'] or 0,
            'total_transactions': qs.count(),
            'by_method': list(
                qs.values('payment_method').annotate(
                    count=Count('id'), total=Sum('amount')
                )
            ),
            'refunds_total': Payment.objects.filter(is_refunded=True).aggregate(
                total=Sum('refund_amount')
            )['total'] or 0,
        }
        return Response(data)


class InitiatePaymentView(generics.GenericAPIView):
    serializer_class = PaymentInitiateSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            filing = TaxFiling.objects.get(id=data['tax_filing_id'])
        except TaxFiling.DoesNotExist:
            return Response({'error': 'Tax filing not found.'}, status=404)

        if filing.user != request.user and not request.user.is_tax_officer:
            return Response({'error': 'Not authorized.'}, status=403)

        if filing.status not in [TaxFiling.FilingStatus.APPROVED, TaxFiling.FilingStatus.OVERDUE]:
            return Response({'error': 'Filing must be approved before payment.'}, status=400)

        amount = data['amount']
        if amount > filing.balance_due:
            return Response({'error': f'Amount exceeds balance due: {filing.balance_due} ETB.'}, status=400)

        # Create pending payment
        payment = Payment.objects.create(
            tax_filing=filing,
            user=request.user,
            amount=amount,
            payment_method=data['payment_method'],
            notes=data.get('notes', ''),
            status=Payment.PaymentStatus.PROCESSING,
        )

        # Process via gateway
        gateway = get_gateway(data['payment_method'])
        gateway_result = gateway.process_payment(
            amount=amount,
            reference=filing.reference_number,
            phone_number=data.get('phone_number'),
            bank_account=data.get('bank_account'),
        )

        # Log gateway interaction
        PaymentGatewayLog.objects.create(
            payment=payment,
            gateway=data['payment_method'],
            request_data={'amount': float(amount), 'reference': filing.reference_number},
            response_data=gateway_result,
        )

        if gateway_result.get('success'):
            payment.status = Payment.PaymentStatus.COMPLETED
            payment.transaction_id = gateway_result.get('transaction_id')
            payment.payment_date = timezone.now()
            payment.save()  # triggers receipt_number generation

            # Update filing
            filing.amount_paid += amount
            if filing.amount_paid >= filing.total_due:
                filing.status = TaxFiling.FilingStatus.PAID
            filing.save()

            send_payment_confirmation.delay(str(payment.id))

            return Response({
                'message': 'Payment successful.',
                'receipt_number': payment.receipt_number,
                'transaction_id': payment.transaction_id,
                'amount': float(amount),
                'status': payment.status,
            }, status=status.HTTP_201_CREATED)
        else:
            payment.status = Payment.PaymentStatus.FAILED
            payment.failure_reason = gateway_result.get('error', 'Unknown error')
            payment.save()
            return Response({
                'error': 'Payment failed.',
                'details': gateway_result.get('error'),
            }, status=400)
