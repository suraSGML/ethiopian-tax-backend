"""
Audit Middleware - logs all API requests automatically.
"""
import json
import threading
from django.utils.deprecation import MiddlewareMixin

_thread_local = threading.local()


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditMiddleware(MiddlewareMixin):
    """
    Logs significant API actions to the audit log.
    Only logs authenticated requests to sensitive endpoints.
    """
    TRACKED_PATHS = [
        '/api/v1/auth/',
        '/api/v1/tax/',
        '/api/v1/payments/',
    ]

    WRITE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    def process_response(self, request, response):
        try:
            if not any(request.path.startswith(p) for p in self.TRACKED_PATHS):
                return response
            if request.method not in self.WRITE_METHODS:
                return response
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return response

            action = self._determine_action(request)
            if action:
                from .models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    description=f'{request.method} {request.path}',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    endpoint=request.path,
                    method=request.method,
                    status_code=response.status_code,
                )
        except Exception:
            pass  # Never break the request cycle
        return response

    def _determine_action(self, request):
        path = request.path
        method = request.method
        if 'login' in path:
            return 'login'
        if 'logout' in path:
            return 'logout'
        if 'register' in path:
            return 'register'
        if 'change-password' in path:
            return 'password_change'
        if 'filings' in path and method == 'POST':
            return 'filing_create'
        if 'submit' in path:
            return 'filing_submit'
        if 'review' in path:
            return 'filing_review'
        if 'payments' in path and 'initiate' in path:
            return 'payment_initiate'
        if 'refund' in path:
            return 'refund'
        if 'profile' in path:
            return 'profile_update'
        return 'admin_action'
