from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers
from . import views

router = DefaultRouter()
router.register('filings', views.TaxFilingViewSet, basename='filings')
router.register('certificates', views.ComplianceCertificateViewSet, basename='certificates')
router.register('announcements', views.SystemAnnouncementViewSet, basename='announcements')

# Ethiopian Tax Workflow Endpoints
router.register('assessments', views.TaxAssessmentNoticeViewSet, basename='assessments')
router.register('receipts', views.OfficialPaymentReceiptViewSet, basename='receipts')
router.register('clearance-certificates', views.TaxClearanceCertificateViewSet, basename='clearance-certificates')
router.register('withholding-certificates', views.WithholdingTaxCertificateViewSet, basename='withholding-certificates')
router.register('vat-refunds', views.VATRefundApplicationViewSet, basename='vat-refunds')
router.register('objections', views.TaxObjectionViewSet, basename='objections')
router.register('tribunal-cases', views.TaxTribunalCaseViewSet, basename='tribunal-cases')

filings_router = nested_routers.NestedDefaultRouter(router, 'filings', lookup='filing')
filings_router.register('documents', views.TaxFilingDocumentViewSet, basename='filing-documents')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(filings_router.urls)),
    path('calculate/', views.TaxCalculationView.as_view(), name='tax-calculate'),
]
