from rest_framework.permissions import BasePermission
from .models import User


class IsTaxpayer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.TAXPAYER


class IsTaxOfficer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            User.Role.TAX_OFFICER, User.Role.SUPER_ADMIN
        ]


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in [User.Role.TAX_OFFICER, User.Role.SUPER_ADMIN]:
            return True
        return obj.user == request.user or obj == request.user
