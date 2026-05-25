from django.http import JsonResponse
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
def home(request):
    return JsonResponse({"message": "API is running"})
urlpatterns = [
    path("", home),
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/tax/', include('tax_filing.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/audit/', include('audit.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/core/', include('core.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
