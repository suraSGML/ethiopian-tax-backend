"""
PDF Receipt Generator using ReportLab
Falls back to a plain-text receipt if ReportLab is unavailable.
"""
import io
from django.utils import timezone

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


def generate_pdf_receipt(payment) -> bytes:
    """Generate a PDF receipt. Falls back to plain text if ReportLab unavailable."""
    if not REPORTLAB_AVAILABLE:
        return _generate_text_receipt(payment)
    return _generate_pdf_receipt_reportlab(payment)


def _generate_text_receipt(payment) -> bytes:
    """Plain text fallback receipt."""
    filing = payment.tax_filing
    user = payment.user
    lines = [
        "=" * 60,
        "FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA",
        "MINISTRY OF REVENUE - OFFICIAL PAYMENT RECEIPT",
        "=" * 60,
        f"Receipt Number : {payment.receipt_number or 'N/A'}",
        f"Transaction ID : {payment.transaction_id or 'N/A'}",
        f"Date           : {payment.payment_date.strftime('%d %b %Y %H:%M') if payment.payment_date else 'N/A'}",
        "-" * 60,
        f"Taxpayer Name  : {user.get_full_name()}",
        f"TIN            : {user.tin or 'N/A'}",
        f"Email          : {user.email}",
        "-" * 60,
        f"Filing Ref     : {filing.reference_number or 'N/A'}",
        f"Tax Type       : {filing.get_tax_type_display()}",
        f"Fiscal Year    : {filing.fiscal_year}",
        f"Payment Method : {payment.get_payment_method_display()}",
        f"Amount Paid    : ETB {payment.amount:,.2f}",
        "=" * 60,
        f"Generated: {timezone.now().strftime('%d %B %Y at %H:%M:%S')} (EAT)",
    ]
    return "\n".join(lines).encode("utf-8")


def _generate_pdf_receipt_reportlab(payment) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#1a5276'), alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#2e86c1'), alignment=TA_CENTER)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=TA_CENTER)
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')

    story = []

    # Header
    story.append(Paragraph('FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA', header_style))
    story.append(Paragraph('MINISTRY OF REVENUE', title_style))
    story.append(Paragraph('Digital Tax Payment System', subtitle_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1a5276')))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph('OFFICIAL PAYMENT RECEIPT', ParagraphStyle('ReceiptTitle', parent=styles['Normal'], fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER)))
    story.append(Spacer(1, 0.5*cm))

    # Receipt details table
    filing = payment.tax_filing
    user = payment.user

    receipt_data = [
        ['Receipt Number:', payment.receipt_number or 'N/A', 'Date:', payment.payment_date.strftime('%d %b %Y %H:%M') if payment.payment_date else 'N/A'],
        ['Transaction ID:', payment.transaction_id or 'N/A', 'Status:', payment.status.upper()],
    ]

    receipt_table = Table(receipt_data, colWidths=[4*cm, 7*cm, 3*cm, 4*cm])
    receipt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eaf2ff')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(receipt_table)
    story.append(Spacer(1, 0.5*cm))

    # Taxpayer info
    story.append(Paragraph('TAXPAYER INFORMATION', ParagraphStyle('SectionTitle', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a5276'))))
    story.append(Spacer(1, 0.2*cm))

    taxpayer_data = [
        ['Full Name:', user.get_full_name()],
        ['TIN:', user.tin or 'N/A'],
        ['Email:', user.email],
        ['Phone:', str(user.phone) if user.phone else 'N/A'],
    ]
    taxpayer_table = Table(taxpayer_data, colWidths=[4*cm, 14*cm])
    taxpayer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(taxpayer_table)
    story.append(Spacer(1, 0.5*cm))

    # Payment details
    story.append(Paragraph('PAYMENT DETAILS', ParagraphStyle('SectionTitle', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a5276'))))
    story.append(Spacer(1, 0.2*cm))

    payment_data = [
        ['Filing Reference:', filing.reference_number or 'N/A'],
        ['Tax Type:', filing.get_tax_type_display()],
        ['Fiscal Year:', str(filing.fiscal_year)],
        ['Payment Method:', payment.get_payment_method_display()],
        ['Amount Paid:', f'ETB {payment.amount:,.2f}'],
    ]
    payment_table = Table(payment_data, colWidths=[4*cm, 14*cm])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('FONTNAME', (-1, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-1, -1), (-1, -1), 11),
        ('TEXTCOLOR', (-1, -1), (-1, -1), colors.HexColor('#1a5276')),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 1*cm))

    # Footer
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        'This is an official receipt issued by the Ethiopian Ministry of Revenue Digital Tax System.',
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        f'Generated on: {timezone.now().strftime("%d %B %Y at %H:%M:%S")} (EAT)',
        ParagraphStyle('Footer2', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
