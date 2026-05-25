from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('logs', views.AuditLogViewSet, basename='audit-logs')
router.register('fraud-alerts', views.FraudAlertViewSet, basename='fraud-alerts')

urlpatterns = [
    path('', include(router.urls)),
]
