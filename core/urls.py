from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/taxpayer/', views.TaxpayerDashboardView.as_view(), name='taxpayer-dashboard'),
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('reports/revenue/', views.RevenueReportView.as_view(), name='revenue-report'),
]
