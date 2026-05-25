from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Sum
from drf_spectacular.utils import extend_schema
import uuid

from .models import (
    TaxFiling, TaxFilingDocument, TaxCalculationLog,
    FilingStatusHistory, ComplianceCertificate, SystemAnnouncement,
    TaxAssessmentNotice, OfficialPaymentReceipt, TaxClearanceCertificate,
    WithholdingTaxCertificate, VATRefundApplication, TaxObjection, TaxTribunalCase
)
from .serializers import (
    TaxFilingSerializer, TaxFilingCreateSerializer, TaxFilingDocumentSerializer,
    TaxFilingReviewSerializer, TaxCalculationRequestSerializer,
    FilingStatusHistorySerializer, ComplianceCertificateSerializer,
    SystemAnnouncementSerializer,
    TaxAssessmentNoticeSerializer, TaxAssessmentNoticeCreateSerializer,
    OfficialPaymentReceiptSerializer,
    TaxClearanceCertificateSerializer, TaxClearanceCertificateCreateSerializer,
    WithholdingTaxCertificateSerializer, WithholdingTaxCertificateCreateSerializer,
    VATRefundApplicationSerializer, VATRefundApplicationCreateSerializer,
    TaxObjectionSerializer, TaxObjectionCreateSerializer, TaxObjectionReviewSerializer,
    TaxTribunalCaseSerializer, TaxTribunalCaseCreateSerializer,
)
from .tax_calculator import (
    calculate_personal_income_tax, calculate_business_income_tax,
    calculate_vat, calculate_turnover_tax, calculate_penalty
)
from .workflow import (
    submit_filing, approve_filing, reject_filing,
    appeal_filing, create_amendment, apply_penalty,
    get_compliance_score, can_issue_compliance_certificate,
)
from accounts.permissions import IsTaxOfficer, IsTaxpayer, IsSuperAdmin


class TaxFilingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['tax_type', 'status', 'fiscal_year', 'filing_period', 'is_amendment']
    search_fields = ['reference_number', 'user__tin', 'user__email']
    ordering_fields = ['created_at', 'due_date', 'total_due', 'submission_date']

    def get_queryset(self):
        user = self.request.user
        qs = TaxFiling.objects.select_related('user', 'reviewed_by', 'original_filing').prefetch_related('documents', 'status_history')
        if user.is_taxpayer:
            return qs.filter(user=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return TaxFilingCreateSerializer
        if self.action == 'review':
            return TaxFilingReviewSerializer
        return TaxFilingSerializer

    def get_permissions(self):
        if self.action in ['review', 'summary', 'list_all', 'resolve_appeal']:
            return [IsTaxOfficer()]
        if self.action in ['issue_certificate']:
            return [IsTaxOfficer()]
        return [IsAuthenticated()]

    # ── Taxpayer actions ──────────────────────────────────────

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        filing = self.get_object()
        try:
            submit_filing(filing, request.user, request)
        except (ValueError, PermissionError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Notify tax officers about the new submission
        try:
            from notifications.tasks import notify_officers_filing_submitted
            notify_officers_filing_submitted.delay(str(filing.id))
        except Exception:
            pass
        
        return Response({
            'message': 'Filing submitted successfully. A tax officer will review it shortly.',
            'reference_number': filing.reference_number,
            'status': filing.status,
            'is_late': filing.is_late_submission,
            'days_late': filing.days_late,
        })

    @action(detail=True, methods=['post'])
    def appeal(self, request, pk=None):
        """Taxpayer appeals a rejected filing."""
        filing = self.get_object()
        appeal_reason = request.data.get('appeal_reason', '').strip()
        try:
            appeal_filing(filing, request.user, appeal_reason, request)
        except (ValueError, PermissionError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'message': 'Your appeal has been submitted. A senior officer will review it within 5 business days.',
            'reference_number': filing.reference_number,
            'status': filing.status,
            'appeal_date': filing.appeal_date,
        })

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        """Taxpayer files an amendment to a paid/approved filing."""
        original = self.get_object()
        amendment_reason = request.data.get('amendment_reason', '').strip()
        new_data = {
            'gross_income': request.data.get('gross_income', original.gross_income),
            'allowable_deductions': request.data.get('allowable_deductions', original.allowable_deductions),
            'vat_collected': request.data.get('vat_collected', original.vat_collected),
            'vat_paid': request.data.get('vat_paid', original.vat_paid),
        }
        try:
            amendment = create_amendment(original, request.user, amendment_reason, new_data, request)
        except (ValueError, PermissionError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'message': 'Amendment filing created as a draft. Please review and submit.',
            'amendment_reference': amendment.reference_number,
            'amendment_id': str(amendment.id),
            'original_reference': original.reference_number,
        }, status=status.HTTP_201_CREATED)

    # ── Officer actions ───────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def review(self, request, pk=None):
        """Officer approves or rejects a filing."""
        filing = self.get_object()
        decision = request.data.get('status')
        notes = request.data.get('review_notes', '')
        reason = request.data.get('rejection_reason', '')

        try:
            if decision == 'approved':
                approve_filing(filing, request.user, notes, request)
            elif decision == 'rejected':
                reject_filing(filing, request.user, reason, notes, request)
            elif decision == 'under_review':
                from .workflow import record_status_change
                old = filing.status
                filing.status = 'under_review'
                filing.reviewed_by = request.user
                filing.save()
                record_status_change(filing, old, 'under_review', request.user, notes, request)
            else:
                return Response({'error': 'Invalid decision. Use: approved, rejected, under_review'}, status=400)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': f'Filing {decision}.', 'status': filing.status})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def resolve_appeal(self, request, pk=None):
        """Officer resolves an appeal — upheld (approve) or dismissed (keep rejected)."""
        filing = self.get_object()
        if filing.status != 'appealed':
            return Response({'error': 'Filing is not under appeal.'}, status=400)

        outcome = request.data.get('outcome')  # 'upheld' or 'dismissed'
        notes = request.data.get('notes', '')

        if outcome not in ['upheld', 'dismissed']:
            return Response({'error': 'Outcome must be "upheld" or "dismissed".'}, status=400)

        from .workflow import record_status_change
        old_status = filing.status
        filing.appeal_outcome = outcome
        filing.appeal_resolved_at = timezone.now()

        if outcome == 'upheld':
            filing.status = 'approved'
            filing.review_notes = notes
            filing.reviewed_by = request.user
            filing.reviewed_at = timezone.now()
            msg = 'Appeal upheld. Filing approved.'
        else:
            filing.status = 'rejected'
            msg = 'Appeal dismissed. Filing remains rejected.'

        filing.save()
        record_status_change(filing, old_status, filing.status, request.user,
                             f'Appeal {outcome}: {notes}', request)

        # Notify taxpayer
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=filing.user,
                notification_type='filing_approved' if outcome == 'upheld' else 'filing_rejected',
                channel='in_app',
                title=f'Appeal {"Upheld ✓" if outcome == "upheld" else "Dismissed ✗"} — {filing.reference_number}',
                message=notes or msg,
                extra_data={'filing_id': str(filing.id)},
            )
        except Exception:
            pass

        return Response({'message': msg, 'outcome': outcome, 'status': filing.status})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def apply_penalty(self, request, pk=None):
        filing = self.get_object()
        try:
            apply_penalty(filing, request.user, request)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response({
            'message': 'Penalty applied.',
            'penalty_amount': float(filing.penalty_amount),
            'late_fee': float(filing.late_fee),
            'total_due': float(filing.total_due),
            'days_overdue': filing.days_late,
        })

    @action(detail=False, methods=['get'])
    def my_compliance(self, request):
        """Taxpayer's own compliance score."""
        score = get_compliance_score(request.user)
        eligible, reason = can_issue_compliance_certificate(request.user)
        score['certificate_eligible'] = eligible
        score['certificate_reason'] = reason
        return Response(score)

    @action(detail=False, methods=['get'], permission_classes=[IsTaxOfficer])
    def summary(self, request):
        qs = TaxFiling.objects.all()
        data = {
            'total_filings': qs.count(),
            'by_status': {s: qs.filter(status=s).count() for s, _ in TaxFiling.FilingStatus.choices},
            'by_type': {t: qs.filter(tax_type=t).count() for t, _ in TaxFiling.TaxType.choices},
            'total_tax_due': qs.aggregate(total=Sum('total_due'))['total'] or 0,
            'total_collected': qs.aggregate(total=Sum('amount_paid'))['total'] or 0,
            'pending_appeals': qs.filter(status='appealed').count(),
            'amendments': qs.filter(is_amendment=True).count(),
        }
        return Response(data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Full status history of a filing."""
        filing = self.get_object()
        history = filing.status_history.select_related('changed_by').all()
        serializer = FilingStatusHistorySerializer(history, many=True)
        return Response(serializer.data)


class TaxCalculationView(generics.GenericAPIView):
    serializer_class = TaxCalculationRequestSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tax_type = data['tax_type']

        if tax_type == TaxFiling.TaxType.PERSONAL_INCOME:
            result = calculate_personal_income_tax(data['gross_income'])
        elif tax_type == TaxFiling.TaxType.BUSINESS_INCOME:
            result = calculate_business_income_tax(data['gross_income'], data['allowable_deductions'])
        elif tax_type == TaxFiling.TaxType.VAT:
            result = calculate_vat(data['vat_collected'], data['vat_paid'])
        elif tax_type == TaxFiling.TaxType.TURNOVER:
            result = calculate_turnover_tax(data['gross_income'], data.get('business_type', 'trade'))
        else:
            result = {'error': 'Unsupported tax type for direct calculation.'}

        if data.get('days_overdue', 0) > 0 and 'calculated_tax' in result:
            from decimal import Decimal
            penalty = calculate_penalty(Decimal(str(result.get('calculated_tax', 0))), data['days_overdue'])
            result['penalty_details'] = penalty

        return Response(result)


class TaxFilingDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = TaxFilingDocumentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        filing_id = self.kwargs.get('filing_pk')
        try:
            uuid.UUID(filing_id)
        except (ValueError, TypeError, AttributeError):
            return TaxFilingDocument.objects.none()
        return TaxFilingDocument.objects.filter(filing_id=filing_id).order_by('-uploaded_at')

    def perform_create(self, serializer):
        filing_id = self.kwargs.get('filing_pk')
        try:
            uuid.UUID(filing_id)
        except (ValueError, TypeError, AttributeError):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'filing_pk': 'Invalid filing ID format.'})
        filing = TaxFiling.objects.get(id=filing_id)
        if filing.user != self.request.user and not self.request.user.is_tax_officer:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only upload documents to your own filings.')
        serializer.save(filing=filing)


class ComplianceCertificateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ComplianceCertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_taxpayer:
            return ComplianceCertificate.objects.filter(user=user)
        return ComplianceCertificate.objects.all()

    @action(detail=False, methods=['post'], permission_classes=[IsTaxOfficer])
    def issue(self, request):
        """Officer issues a compliance certificate to a taxpayer."""
        from accounts.models import User
        from datetime import date, timedelta

        user_id = request.data.get('user_id')
        fiscal_year = request.data.get('fiscal_year', timezone.now().year)

        try:
            taxpayer = User.objects.get(id=user_id, role='taxpayer')
        except User.DoesNotExist:
            return Response({'error': 'Taxpayer not found.'}, status=404)

        eligible, reason = can_issue_compliance_certificate(taxpayer)
        if not eligible:
            return Response({'error': reason}, status=400)

        # Invalidate old certificates
        ComplianceCertificate.objects.filter(user=taxpayer, is_valid=True).update(
            is_valid=False, revoked_at=timezone.now(), revoke_reason='Superseded by new certificate'
        )

        cert = ComplianceCertificate.objects.create(
            user=taxpayer,
            issued_by=request.user,
            fiscal_year=fiscal_year,
            valid_until=date.today() + timedelta(days=365),
        )

        # Notify taxpayer
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=taxpayer,
                notification_type='general',
                channel='in_app',
                title='🏆 Compliance Certificate Issued',
                message=f'Your Tax Compliance Certificate {cert.certificate_number} has been issued. Valid until {cert.valid_until}.',
                extra_data={'certificate_number': cert.certificate_number},
            )
        except Exception:
            pass

        return Response(ComplianceCertificateSerializer(cert).data, status=201)


class SystemAnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = SystemAnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        qs = SystemAnnouncement.objects.filter(
            is_active=True,
            show_from__lte=now,
        ).filter(
            Q(show_until__isnull=True) | Q(show_until__gte=now)
        )
        if user.is_taxpayer:
            qs = qs.filter(target_role__in=['all', 'taxpayer'])
        elif user.is_tax_officer:
            qs = qs.filter(target_role__in=['all', 'tax_officer'])
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]


# ─── Ethiopian Tax Workflow ViewSets ─────────────────────────────────────────────

class TaxAssessmentNoticeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'assessment_date', 'filing']
    search_fields = ['assessment_number', 'filing__reference_number']
    ordering_fields = ['assessment_date', 'valid_until']

    def get_queryset(self):
        user = self.request.user
        qs = TaxAssessmentNotice.objects.select_related('filing', 'assessed_by')
        if user.is_taxpayer:
            return qs.filter(filing__user=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return TaxAssessmentNoticeCreateSerializer
        return TaxAssessmentNoticeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTaxOfficer()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Taxpayer accepts the assessment."""
        notice = self.get_object()
        if notice.status != 'pending':
            return Response({'error': 'Only pending assessments can be accepted.'}, status=400)
        if notice.filing.user != request.user:
            return Response({'error': 'Not authorized.'}, status=403)
        
        notice.status = 'accepted'
        notice.accepted_at = timezone.now()
        notice.save()
        
        # Update filing status
        notice.filing.status = 'approved'
        notice.filing.reviewed_by = notice.assessed_by
        notice.filing.reviewed_at = timezone.now()
        notice.filing.save()
        
        return Response({'message': 'Assessment accepted.', 'assessment_number': notice.assessment_number})

    @action(detail=True, methods=['post'])
    def object_to(self, request, pk=None):
        """Taxpayer objects to the assessment."""
        notice = self.get_object()
        if notice.status != 'pending':
            return Response({'error': 'Only pending assessments can be objected.'}, status=400)
        if notice.filing.user != request.user:
            return Response({'error': 'Not authorized.'}, status=403)
        
        objection_reason = request.data.get('objection_reason', '').strip()
        if not objection_reason or len(objection_reason) < 20:
            return Response({'error': 'Objection reason must be at least 20 characters.'}, status=400)
        
        notice.status = 'objected'
        notice.objected_at = timezone.now()
        notice.objection_reason = objection_reason
        notice.save()
        
        return Response({'message': 'Assessment objected. You may file a formal objection.'})


class OfficialPaymentReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['receipt_date', 'status', 'taxpayer']
    search_fields = ['receipt_number', 'verification_code']
    ordering_fields = ['receipt_date']

    def get_queryset(self):
        user = self.request.user
        qs = OfficialPaymentReceipt.objects.select_related('payment', 'taxpayer', 'issued_by')
        if user.is_taxpayer:
            return qs.filter(taxpayer=user)
        return qs

    serializer_class = OfficialPaymentReceiptSerializer

    @action(detail=True, methods=['get'])
    def verify(self, request, pk=None):
        """Verify receipt using verification code."""
        receipt = self.get_object()
        return Response({
            'valid': receipt.status == 'issued',
            'receipt_number': receipt.receipt_number,
            'amount': float(receipt.amount_paid),
            'taxpayer': receipt.taxpayer_tin,
            'verified_at': receipt.verified_at
        })


class TaxClearanceCertificateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'purpose', 'issued_date']
    search_fields = ['certificate_number', 'verification_code']
    ordering_fields = ['issued_date', 'expiry_date']

    def get_queryset(self):
        user = self.request.user
        qs = TaxClearanceCertificate.objects.select_related('user', 'issued_by')
        if user.is_taxpayer:
            return qs.filter(user=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return TaxClearanceCertificateCreateSerializer
        return TaxClearanceCertificateSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsTaxOfficer()]
        if self.action in ['update', 'partial_update']:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'])
    def verify(self, request, pk=None):
        """Verify certificate using verification code."""
        cert = self.get_object()
        return Response({
            'valid': cert.status == 'issued' and not cert.is_expired,
            'certificate_number': cert.certificate_number,
            'purpose': cert.purpose,
            'valid_for': cert.valid_for,
            'expiry_date': cert.expiry_date,
            'total_tax_paid': float(cert.total_tax_paid)
        })


class WithholdingTaxCertificateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'purpose', 'certificate_date', 'fiscal_year']
    search_fields = ['certificate_number', 'verification_code', 'recipient_tin']
    ordering_fields = ['certificate_date']

    def get_queryset(self):
        user = self.request.user
        qs = WithholdingTaxCertificate.objects.select_related('withholding_agent', 'recipient', 'issued_by')
        if user.is_taxpayer:
            return qs.filter(Q(withholding_agent=user) | Q(recipient=user))
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return WithholdingTaxCertificateCreateSerializer
        return WithholdingTaxCertificateSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsTaxOfficer()]
        if self.action in ['update', 'partial_update']:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """Issue the certificate (mark as issued)."""
        cert = self.get_object()
        if cert.status != 'generated':
            return Response({'error': 'Only generated certificates can be issued.'}, status=400)
        
        cert.status = 'issued'
        cert.issued_at = timezone.now()
        cert.save()
        
        return Response({'message': 'Certificate issued.', 'certificate_number': cert.certificate_number})


class VATRefundApplicationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'refund_period', 'fiscal_year', 'application_date']
    search_fields = ['application_number']
    ordering_fields = ['application_date']

    def get_queryset(self):
        user = self.request.user
        qs = VATRefundApplication.objects.select_related('business', 'reviewed_by')
        if user.is_taxpayer:
            return qs.filter(business=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return VATRefundApplicationCreateSerializer
        return VATRefundApplicationSerializer

    def get_permissions(self):
        if self.action in ['review', 'approve', 'reject']:
            return [IsTaxOfficer()]
        if self.action in ['create']:
            return [IsTaxpayer()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def review(self, request, pk=None):
        """Officer reviews the refund application."""
        application = self.get_object()
        if application.status != 'submitted':
            return Response({'error': 'Only submitted applications can be reviewed.'}, status=400)
        
        application.status = 'under_review'
        application.reviewed_by = request.user
        application.review_date = timezone.now()
        application.review_notes = request.data.get('review_notes', '')
        application.save()
        
        return Response({'message': 'Application under review.'})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def approve(self, request, pk=None):
        """Officer approves the refund application."""
        application = self.get_object()
        if application.status != 'under_review':
            return Response({'error': 'Only under-review applications can be approved.'}, status=400)
        
        application.status = 'approved'
        application.review_notes = request.data.get('review_notes', '')
        application.save()
        
        return Response({'message': 'Refund approved. Payment will be processed.', 'refund_amount': float(application.refund_amount)})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def reject(self, request, pk=None):
        """Officer rejects the refund application."""
        application = self.get_object()
        if application.status != 'under_review':
            return Response({'error': 'Only under-review applications can be rejected.'}, status=400)
        
        rejection_reason = request.data.get('rejection_reason', '').strip()
        if not rejection_reason or len(rejection_reason) < 10:
            return Response({'error': 'Rejection reason must be at least 10 characters.'}, status=400)
        
        application.status = 'rejected'
        application.rejection_reason = rejection_reason
        application.review_notes = request.data.get('review_notes', '')
        application.save()
        
        return Response({'message': 'Refund rejected.'})


class TaxObjectionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'objection_date']
    search_fields = ['objection_number', 'assessment__assessment_number']
    ordering_fields = ['objection_date']

    def get_queryset(self):
        user = self.request.user
        qs = TaxObjection.objects.select_related('assessment', 'taxpayer', 'reviewed_by')
        if user.is_taxpayer:
            return qs.filter(taxpayer=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return TaxObjectionCreateSerializer
        if self.action == 'review':
            return TaxObjectionReviewSerializer
        return TaxObjectionSerializer

    def get_permissions(self):
        if self.action in ['review', 'resolve']:
            return [IsTaxOfficer()]
        if self.action in ['create']:
            return [IsTaxpayer()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def review(self, request, pk=None):
        """Officer reviews the objection."""
        objection = self.get_object()
        if objection.status != 'submitted':
            return Response({'error': 'Only submitted objections can be reviewed.'}, status=400)
        
        objection.status = 'under_review'
        objection.reviewed_by = request.user
        objection.review_date = timezone.now()
        objection.review_notes = request.data.get('review_notes', '')
        objection.save()
        
        return Response({'message': 'Objection under review.'})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def resolve(self, request, pk=None):
        """Officer resolves the objection (accept or reject)."""
        objection = self.get_object()
        if objection.status != 'under_review':
            return Response({'error': 'Only under-review objections can be resolved.'}, status=400)
        
        outcome = request.data.get('outcome')  # accepted or rejected
        review_notes = request.data.get('review_notes', '')
        revised_assessment = request.data.get('revised_assessment')
        
        if outcome not in ['accepted', 'rejected']:
            return Response({'error': 'Outcome must be "accepted" or "rejected".'}, status=400)
        
        objection.status = outcome
        objection.outcome = outcome
        objection.review_notes = review_notes
        if revised_assessment:
            objection.revised_assessment = revised_assessment
        objection.save()
        
        # Update assessment status
        if outcome == 'accepted':
            objection.assessment.status = 'accepted'
            objection.assessment.accepted_at = timezone.now()
        else:
            objection.assessment.status = 'expired'
        objection.assessment.save()
        
        return Response({'message': f'Objection {outcome}.', 'outcome': outcome})


class TaxTribunalCaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'filing_date', 'hearing_date']
    search_fields = ['case_number', 'appeal__reference_number']
    ordering_fields = ['filing_date', 'hearing_date']

    def get_queryset(self):
        user = self.request.user
        qs = TaxTribunalCase.objects.select_related('appeal', 'taxpayer', 'tribunal_officer')
        if user.is_taxpayer:
            return qs.filter(taxpayer=user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return TaxTribunalCaseCreateSerializer
        return TaxTribunalCaseSerializer

    def get_permissions(self):
        if self.action in ['schedule', 'decide']:
            return [IsTaxOfficer()]
        if self.action in ['create']:
            return [IsTaxpayer()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def schedule(self, request, pk=None):
        """Officer schedules a hearing."""
        case = self.get_object()
        if case.status != 'filed':
            return Response({'error': 'Only filed cases can be scheduled.'}, status=400)
        
        hearing_date = request.data.get('hearing_date')
        if not hearing_date:
            return Response({'error': 'Hearing date is required.'}, status=400)
        
        case.status = 'scheduled'
        case.hearing_date = hearing_date
        case.tribunal_officer = request.user
        case.save()
        
        return Response({'message': 'Hearing scheduled.', 'hearing_date': hearing_date})

    @action(detail=True, methods=['post'], permission_classes=[IsTaxOfficer])
    def decide(self, request, pk=None):
        """Officer records the tribunal decision."""
        case = self.get_object()
        if case.status not in ['scheduled', 'in_progress']:
            return Response({'error': 'Case must be scheduled or in progress.'}, status=400)
        
        decision = request.data.get('decision', '').strip()
        outcome = request.data.get('outcome')
        revised_tax_amount = request.data.get('revised_tax_amount')
        
        if not decision or len(decision) < 20:
            return Response({'error': 'Decision must be at least 20 characters.'}, status=400)
        if outcome not in ['upheld', 'dismissed', 'modified', 'settled']:
            return Response({'error': 'Invalid outcome.'}, status=400)
        
        case.status = 'decided'
        case.decision = decision
        case.decision_date = timezone.now()
        case.outcome = outcome
        if revised_tax_amount:
            case.revised_tax_amount = revised_tax_amount
        case.save()
        
        # Update appeal based on outcome
        if outcome == 'upheld':
            case.appeal.status = 'approved'
            case.appeal.review_notes = f'Tribunal upheld appeal: {decision[:100]}'
        elif outcome == 'dismissed':
            case.appeal.status = 'rejected'
            case.appeal.review_notes = f'Tribunal dismissed appeal: {decision[:100]}'
        elif outcome == 'modified':
            case.appeal.status = 'approved'
            case.appeal.review_notes = f'Tribunal modified assessment: {decision[:100]}'
        case.appeal.save()
        
        return Response({'message': f'Case decided: {outcome}.', 'outcome': outcome})
