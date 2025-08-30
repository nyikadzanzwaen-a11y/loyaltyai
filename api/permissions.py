from rest_framework import permissions

class IsBusinessAdmin(permissions.BasePermission):
    """
    Permission to only allow business administrators.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_business_admin

class IsSuperAdmin(permissions.BasePermission):
    """
    Permission to only allow platform super administrators.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_platform_admin

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object or administrators to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Allow administrators to access
        if request.user.is_authenticated and (request.user.is_business_admin or request.user.is_platform_admin):
            return True
            
        # If the object has a customer field
        if hasattr(obj, 'customer'):
            return obj.customer == request.user
            
        # If the object has a user field
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        # By default, deny access
        return False