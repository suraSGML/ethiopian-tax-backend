from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('', views.PaymentViewSet, basename='payments')

urlpatterns = [
    path('initiate/', views.InitiatePaymentView.as_view(), name='initiate-payment'),
    path('', include(router.urls)),
]
