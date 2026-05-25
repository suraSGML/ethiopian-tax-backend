"""
Government Tax Portal — Real Workflow Engine
Handles all state transitions with proper validation, audit trails, and notifications.
"""
from django.utils import timezone
from django.db import transaction
from decimal import Decimal


def record_status_change(filing, from_status, to_status, changed_by, reason='', request=None):
    """Record every status change in the audit trail."""
    from .models import FilingStatusHistory
    ip = None
    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
    FilingStatusHistory.objects.create(
        filing=filing,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
        ip_address=ip,
    )


@transaction.atomic
def submit_filing(filing, user, request=None):
    """
    Taxpayer submits a draft filing.
    Validates: not already submitted, due date check, basic data integrity.
    """
    if filing.status != 'draft':
        raise ValueError(f'Cannot submit a filing with status "{filing.status}". Only drafts can be submitted.')
    if filing.user != user:
        raise PermissionError('You can only submit your own filings.')
    if filing.calculated_tax < 0:
        raise ValueError('Calculated tax cannot be negative.')

    # Check if late
    if filing.due_date and filing.due_date < timezone.now().date():
        days_late = (timezone.now().date() - filing.due_date).days
        filing.is_late_submission = True
        filing.days_late = days_late

    old_status = filing.status
    filing.status = 'submitted'
    filing.submission_date = timezone.now()
    filing.save()

    record_status_change(filing, old_status, 'submitted', user, 'Taxpayer submitted filing', request)

    # Notify
    try:
        from notifications.tasks import send_filing_status_notification
        send_filing_status_notification.delay(str(filing.id))
    except Exception:
        pass

    return filing


@transaction.atomic
def approve_filing(filing, officer, notes='', request=None):
    """Officer approves a submitted or under-review filing."""
    if filing.status not in ['submitted', 'under_review', 'appealed']:
        raise ValueError(f'Cannot approve a filing with status "{filing.status}".')

    old_status = filing.status
    filing.status = 'approved'
    filing.review_notes = notes
    filing.reviewed_by = officer
    filing.reviewed_at = timezone.now()
    filing.save()

    record_status_change(filing, old_status, 'approved', officer, notes or 'Filing approved', request)

    try:
        from notifications.tasks import send_filing_status_notification
        send_filing_status_notification.delay(str(filing.id))
    except Exception:
        pass

    return filing


@transaction.atomic
def reject_filing(filing, officer, reason, notes='', request=None):
    """
    Officer rejects a filing with a mandatory reason.
    Taxpayer has 30 days to appeal.
    """
    if not reason or len(reason.strip()) < 10:
        raise ValueError('A rejection reason of at least 10 characters is required.')
    if filing.status not in ['submitted', 'under_review']:
        raise ValueError(f'Cannot reject a filing with status "{filing.status}".')

    old_status = filing.status
    filing.status = 'rejected'
    filing.rejection_reason = reason
    filing.review_notes = notes
    filing.reviewed_by = officer
    filing.reviewed_at = timezone.now()
    filing.save()

    record_status_change(filing, old_status, 'rejected', officer, reason, request)

    try:
        from notifications.tasks import send_filing_status_notification
        send_filing_status_notification.delay(str(filing.id))
    except Exception:
        pass

    return filing


@transaction.atomic
def appeal_filing(filing, user, appeal_reason, request=None):
    """
    Taxpayer appeals a rejected filing.
    Must be within 30 days of rejection.
    Must provide a reason.
    """
    if filing.status != 'rejected':
        raise ValueError('Only rejected filings can be appealed.')
    if filing.user != user:
        raise PermissionError('You can only appeal your own filings.')
    if not filing.can_be_appealed:
        raise ValueError('The 30-day appeal window has expired.')
    if not appeal_reason or len(appeal_reason.strip()) < 20:
        raise ValueError('Appeal reason must be at least 20 characters.')

    old_status = filing.status
    filing.status = 'appealed'
    filing.appeal_reason = appeal_reason
    filing.appeal_date = timezone.now()
    filing.save()

    record_status_change(filing, old_status, 'appealed', user, f'Appeal: {appeal_reason[:100]}', request)

    # Create fraud check — appeals can be abused
    try:
        from audit.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='filing_submit',
            description=f'Filing {filing.reference_number} appealed by taxpayer.',
            endpoint='/api/v1/tax/filings/appeal/',
            method='POST',
        )
    except Exception:
        pass

    return filing


@transaction.atomic
def create_amendment(original_filing, user, amendment_reason, new_data, request=None):
    """
    Taxpayer files an amendment to a paid or approved filing.
    Creates a new filing linked to the original.
    Original is marked as 'amended'.
    """
    if not original_filing.can_be_amended:
        raise ValueError(f'Filing with status "{original_filing.status}" cannot be amended.')
    if original_filing.user != user:
        raise PermissionError('You can only amend your own filings.')
    if not amendment_reason or len(amendment_reason.strip()) < 20:
        raise ValueError('Amendment reason must be at least 20 characters.')

    # Create the amendment filing
    amendment = original_filing.__class__(
        user=user,
        tax_type=original_filing.tax_type,
        filing_period=original_filing.filing_period,
        fiscal_year=original_filing.fiscal_year,
        period_month=original_filing.period_month,
        period_quarter=original_filing.period_quarter,
        due_date=original_filing.due_date,
        is_amendment=True,
        original_filing=original_filing,
        amendment_reason=amendment_reason,
        status='draft',
        **new_data,
    )
    amendment.save()

    # Mark original as amended
    old_status = original_filing.status
    original_filing.status = 'amended'
    original_filing.save()

    record_status_change(original_filing, old_status, 'amended', user,
                         f'Amended by {amendment.reference_number}', request)
    record_status_change(amendment, '', 'draft', user,
                         f'Amendment of {original_filing.reference_number}: {amendment_reason[:100]}', request)

    return amendment


@transaction.atomic
def apply_penalty(filing, applied_by=None, request=None):
    """
    Apply penalty and late fees to an overdue filing.
    Called by system scheduler or manually by officer.
    """
    from tax_filing.tax_calculator import calculate_penalty
    if not filing.due_date:
        raise ValueError('Filing has no due date set.')

    today = timezone.now().date()
    if today <= filing.due_date:
        return filing  # Not overdue yet

    days_overdue = (today - filing.due_date).days
    penalty_data = calculate_penalty(filing.calculated_tax, days_overdue)

    old_total = filing.total_due
    filing.penalty_amount = Decimal(str(penalty_data['penalty_amount']))
    filing.late_fee = Decimal(str(penalty_data['late_fee']))
    filing.total_due = filing.calculated_tax + filing.penalty_amount + filing.late_fee
    filing.status = 'overdue'
    filing.penalty_applied_at = timezone.now()
    filing.days_late = days_overdue
    filing.save()

    record_status_change(
        filing, 'approved' if old_total == filing.calculated_tax else filing.status,
        'overdue', applied_by,
        f'Penalty applied: {days_overdue} days overdue. Total: ETB {filing.total_due}',
        request
    )

    # Notify taxpayer
    try:
        from notifications.models import Notification
        Notification.objects.create(
            user=filing.user,
            notification_type='penalty_notice',
            channel='in_app',
            title=f'⚠ Penalty Applied — {filing.reference_number}',
            message=(
                f'Your filing {filing.reference_number} is {days_overdue} days overdue. '
                f'A penalty of ETB {filing.penalty_amount:,.2f} and late fee of ETB {filing.late_fee:,.2f} '
                f'have been applied. Total now due: ETB {filing.total_due:,.2f}.'
            ),
            extra_data={'filing_id': str(filing.id), 'days_overdue': days_overdue},
        )
    except Exception:
        pass

    return filing


def get_compliance_score(user):
    """
    Calculate a taxpayer's compliance score (0–100).
    Used for risk assessment and certificate eligibility.
    """
    from tax_filing.models import TaxFiling
    filings = TaxFiling.objects.filter(user=user)
    total = filings.count()
    if total == 0:
        return {'score': 100, 'grade': 'A', 'label': 'Excellent', 'details': 'No filings yet.'}

    paid = filings.filter(status='paid').count()
    overdue = filings.filter(status='overdue').count()
    rejected = filings.filter(status='rejected').count()
    late_submissions = filings.filter(is_late_submission=True).count()

    # Scoring formula
    score = 100
    score -= (overdue / total) * 40       # Overdue filings: -40 max
    score -= (rejected / total) * 20      # Rejected filings: -20 max
    score -= (late_submissions / total) * 15  # Late submissions: -15 max
    score = max(0, min(100, score))

    if score >= 90:   grade, label = 'A', 'Excellent'
    elif score >= 75: grade, label = 'B', 'Good'
    elif score >= 60: grade, label = 'C', 'Fair'
    elif score >= 40: grade, label = 'D', 'Poor'
    else:             grade, label = 'F', 'Non-Compliant'

    return {
        'score': round(score),
        'grade': grade,
        'label': label,
        'total_filings': total,
        'paid_filings': paid,
        'overdue_filings': overdue,
        'rejected_filings': rejected,
        'late_submissions': late_submissions,
        'eligible_for_certificate': score >= 75 and overdue == 0,
    }


def can_issue_compliance_certificate(user):
    """
    Check if a taxpayer is eligible for a compliance certificate.
    Requirements: score >= 75, no overdue filings, no outstanding balance.
    """
    from tax_filing.models import TaxFiling
    from payments.models import Payment

    compliance = get_compliance_score(user)
    if not compliance['eligible_for_certificate']:
        return False, f'Compliance score {compliance["score"]}/100 is below the required 75.'

    outstanding = TaxFiling.objects.filter(
        user=user, status__in=['approved', 'overdue']
    ).exists()
    if outstanding:
        return False, 'You have outstanding unpaid tax obligations.'

    return True, 'Eligible for compliance certificate.'


# ─── Ethiopian Tax Workflow Functions ───────────────────────────────────────────

@transaction.atomic
def create_assessment_notice(filing, officer, assessment_data, request=None):
    """
    Tax officer creates a formal assessment notice for a filing.
    """
    from .models import TaxAssessmentNotice
    
    assessment = TaxAssessmentNotice.objects.create(
        filing=filing,
        assessed_by=officer,
        taxable_income=assessment_data.get('taxable_income', filing.taxable_income),
        allowable_deductions=assessment_data.get('allowable_deductions', filing.allowable_deductions),
        tax_assessed=assessment_data.get('tax_assessed', filing.calculated_tax),
        penalty_amount=assessment_data.get('penalty_amount', filing.penalty_amount),
        late_fee=assessment_data.get('late_fee', filing.late_fee),
        assessment_breakdown=assessment_data.get('assessment_breakdown', {}),
        assessment_notes=assessment_data.get('assessment_notes', ''),
    )
    
    # Update filing status to under_review
    old_status = filing.status
    filing.status = 'under_review'
    filing.reviewed_by = officer
    filing.reviewed_at = timezone.now()
    filing.save()
    
    record_status_change(filing, old_status, 'under_review', officer, 'Assessment notice issued', request)
    
    return assessment


@transaction.atomic
def accept_assessment(assessment, user, request=None):
    """
    Taxpayer accepts the assessment notice.
    """
    if assessment.status != 'pending':
        raise ValueError('Only pending assessments can be accepted.')
    if assessment.filing.user != user:
        raise PermissionError('You can only accept your own assessments.')
    
    old_status = assessment.status
    assessment.status = 'accepted'
    assessment.accepted_at = timezone.now()
    assessment.save()
    
    # Update filing to approved
    filing = assessment.filing
    filing_old_status = filing.status
    filing.status = 'approved'
    filing.reviewed_by = assessment.assessed_by
    filing.reviewed_at = timezone.now()
    filing.save()
    
    record_status_change(assessment, old_status, 'accepted', user, 'Taxpayer accepted assessment', request)
    record_status_change(filing, filing_old_status, 'approved', user, 'Assessment accepted', request)
    
    return assessment


@transaction.atomic
def object_to_assessment(assessment, user, objection_reason, request=None):
    """
    Taxpayer objects to the assessment notice.
    """
    if assessment.status != 'pending':
        raise ValueError('Only pending assessments can be objected.')
    if assessment.filing.user != user:
        raise PermissionError('You can only object to your own assessments.')
    if not objection_reason or len(objection_reason.strip()) < 20:
        raise ValueError('Objection reason must be at least 20 characters.')
    
    old_status = assessment.status
    assessment.status = 'objected'
    assessment.objected_at = timezone.now()
    assessment.objection_reason = objection_reason
    assessment.save()
    
    record_status_change(assessment, old_status, 'objected', user, f'Objection: {objection_reason[:100]}', request)
    
    return assessment


@transaction.atomic
def create_tax_clearance_certificate(user, purpose, valid_for, officer, request=None):
    """
    Officer creates a tax clearance certificate for a taxpayer.
    """
    from .models import TaxClearanceCertificate, TaxFiling
    
    # Calculate total tax paid and outstanding
    filings = TaxFiling.objects.filter(user=user, status='paid')
    total_paid = sum(f.amount_paid for f in filings)
    outstanding = sum(f.balance_due for f in filings.filter(status__in=['approved', 'overdue']))
    
    if outstanding > 0:
        raise ValueError('Cannot issue clearance certificate with outstanding tax obligations.')
    
    certificate = TaxClearanceCertificate.objects.create(
        user=user,
        purpose=purpose,
        valid_for=valid_for,
        issued_by=officer,
        total_tax_paid=total_paid,
        outstanding_amount=outstanding,
    )
    
    return certificate


@transaction.atomic
def create_withholding_certificate(withholding_agent, recipient_data, officer, request=None):
    """
    Officer creates a withholding tax certificate.
    """
    from .models import WithholdingTaxCertificate
    
    certificate = WithholdingTaxCertificate.objects.create(
        withholding_agent=withholding_agent,
        recipient=recipient_data.get('recipient'),
        recipient_tin=recipient_data.get('recipient_tin'),
        recipient_name=recipient_data.get('recipient_name'),
        amount_withheld=recipient_data.get('amount_withheld'),
        payment_date=recipient_data.get('payment_date'),
        payment_reference=recipient_data.get('payment_reference'),
        gross_amount=recipient_data.get('gross_amount'),
        withholding_rate=recipient_data.get('withholding_rate'),
        purpose=recipient_data.get('purpose'),
        purpose_description=recipient_data.get('purpose_description', ''),
        tax_period=recipient_data.get('tax_period'),
        fiscal_year=recipient_data.get('fiscal_year'),
        issued_by=officer,
    )
    
    return certificate


@transaction.atomic
def submit_vat_refund_application(business, refund_data, request=None):
    """
    Business submits a VAT refund application.
    """
    from .models import VATRefundApplication
    
    application = VATRefundApplication.objects.create(
        business=business,
        refund_period=refund_data.get('refund_period'),
        period_month=refund_data.get('period_month'),
        period_quarter=refund_data.get('period_quarter'),
        fiscal_year=refund_data.get('fiscal_year'),
        input_vat=refund_data.get('input_vat'),
        output_vat=refund_data.get('output_vat'),
        bank_account=refund_data.get('bank_account'),
        bank_name=refund_data.get('bank_name'),
        account_name=refund_data.get('account_name'),
    )
    
    return application


@transaction.atomic
def review_vat_refund(application, officer, review_notes, request=None):
    """
    Officer reviews a VAT refund application.
    """
    if application.status != 'submitted':
        raise ValueError('Only submitted applications can be reviewed.')
    
    application.status = 'under_review'
    application.reviewed_by = officer
    application.review_date = timezone.now()
    application.review_notes = review_notes
    application.save()
    
    return application


@transaction.atomic
def approve_vat_refund(application, officer, review_notes, request=None):
    """
    Officer approves a VAT refund application.
    """
    if application.status != 'under_review':
        raise ValueError('Only under-review applications can be approved.')
    
    application.status = 'approved'
    application.review_notes = review_notes
    application.save()
    
    return application


@transaction.atomic
def reject_vat_refund(application, officer, rejection_reason, review_notes, request=None):
    """
    Officer rejects a VAT refund application.
    """
    if application.status != 'under_review':
        raise ValueError('Only under-review applications can be rejected.')
    if not rejection_reason or len(rejection_reason.strip()) < 10:
        raise ValueError('Rejection reason must be at least 10 characters.')
    
    application.status = 'rejected'
    application.rejection_reason = rejection_reason
    application.review_notes = review_notes
    application.save()
    
    return application


@transaction.atomic
def submit_tax_objection(assessment, taxpayer, objection_reason, request=None):
    """
    Taxpayer submits a formal objection to an assessment.
    """
    from .models import TaxObjection
    
    if assessment.status != 'objected':
        raise ValueError('Can only object to assessments that have been marked as objected.')
    if assessment.filing.user != taxpayer:
        raise PermissionError('You can only object to your own assessments.')
    if not objection_reason or len(objection_reason.strip()) < 20:
        raise ValueError('Objection reason must be at least 20 characters.')
    
    objection = TaxObjection.objects.create(
        assessment=assessment,
        taxpayer=taxpayer,
        objection_reason=objection_reason,
    )
    
    return objection


@transaction.atomic
def review_tax_objection(objection, officer, review_notes, request=None):
    """
    Officer reviews a tax objection.
    """
    if objection.status != 'submitted':
        raise ValueError('Only submitted objections can be reviewed.')
    
    objection.status = 'under_review'
    objection.reviewed_by = officer
    objection.review_date = timezone.now()
    objection.review_notes = review_notes
    objection.save()
    
    return objection


@transaction.atomic
def resolve_tax_objection(objection, officer, outcome, review_notes, revised_assessment=None, request=None):
    """
    Officer resolves a tax objection (accept or reject).
    """
    if objection.status != 'under_review':
        raise ValueError('Only under-review objections can be resolved.')
    if outcome not in ['accepted', 'rejected']:
        raise ValueError('Outcome must be "accepted" or "rejected".')
    
    old_status = objection.status
    objection.status = outcome
    objection.outcome = outcome
    objection.review_notes = review_notes
    if revised_assessment:
        objection.revised_assessment = revised_assessment
    objection.save()
    
    # Update assessment status
    assessment = objection.assessment
    if outcome == 'accepted':
        assessment.status = 'accepted'
        assessment.accepted_at = timezone.now()
        # Update filing
        assessment.filing.status = 'approved'
        assessment.filing.reviewed_by = officer
        assessment.filing.reviewed_at = timezone.now()
        assessment.filing.save()
    else:
        assessment.status = 'expired'
    assessment.save()
    
    record_status_change(objection, old_status, outcome, officer, f'Objection {outcome}: {review_notes[:100]}', request)
    
    return objection


@transaction.atomic
def file_tribunal_case(appeal, taxpayer, request=None):
    """
    Taxpayer files a tribunal case for an appealed filing.
    """
    from .models import TaxTribunalCase
    
    if appeal.status != 'appealed':
        raise ValueError('Can only file tribunal case for appealed filings.')
    if appeal.user != taxpayer:
        raise PermissionError('You can only file tribunal case for your own appeals.')
    
    case = TaxTribunalCase.objects.create(
        appeal=appeal,
        taxpayer=taxpayer,
    )
    
    return case


@transaction.atomic
def schedule_tribunal_hearing(case, officer, hearing_date, request=None):
    """
    Officer schedules a tribunal hearing.
    """
    if case.status != 'filed':
        raise ValueError('Only filed cases can be scheduled.')
    
    case.status = 'scheduled'
    case.hearing_date = hearing_date
    case.tribunal_officer = officer
    case.save()
    
    return case


@transaction.atomic
def decide_tribunal_case(case, officer, decision, outcome, revised_tax_amount=None, request=None):
    """
    Officer records the tribunal decision.
    """
    if case.status not in ['scheduled', 'in_progress']:
        raise ValueError('Case must be scheduled or in progress.')
    if not decision or len(decision.strip()) < 20:
        raise ValueError('Decision must be at least 20 characters.')
    if outcome not in ['upheld', 'dismissed', 'modified', 'settled']:
        raise ValueError('Invalid outcome.')
    
    case.status = 'decided'
    case.decision = decision
    case.decision_date = timezone.now()
    case.outcome = outcome
    if revised_tax_amount:
        case.revised_tax_amount = revised_tax_amount
    case.save()
    
    # Update appeal based on outcome
    appeal = case.appeal
    if outcome == 'upheld':
        appeal.status = 'approved'
        appeal.review_notes = f'Tribunal upheld appeal: {decision[:100]}'
    elif outcome == 'dismissed':
        appeal.status = 'rejected'
        appeal.review_notes = f'Tribunal dismissed appeal: {decision[:100]}'
    elif outcome == 'modified':
        appeal.status = 'approved'
        appeal.review_notes = f'Tribunal modified assessment: {decision[:100]}'
    appeal.save()
    
    return case
