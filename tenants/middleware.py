from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect

from tenants.models import Business

class TenantMiddleware(MiddlewareMixin):
    """Middleware to identify and set the current tenant for each request."""
    
    def process_request(self, request):
        """Process each request to determine and set the current tenant."""
        # Skip tenant identification for admin, static, and media URLs
        if any([
            request.path.startswith('/admin/'),
            request.path.startswith('/static/'),
            request.path.startswith('/media/'),
            request.path.startswith('/api/'),
            request.path == '/',
            request.path.startswith('/accounts/'),
            request.path.startswith('/business/register'),
        ]):
            request.tenant = None
            return None
        
        # Extract tenant slug from subdomain or URL path
        tenant_slug = None
        
        # Method 1: Extract from URL path /business/{slug}/
        path_parts = request.path.split('/')
        if len(path_parts) > 2 and path_parts[1] == 'business':
            tenant_slug = path_parts[2]
        
        if not tenant_slug:
            request.tenant = None
            return None
        
        # Get tenant by slug
        try:
            tenant = Business.objects.get(slug=tenant_slug, is_active=True)
            request.tenant = tenant
        except Business.DoesNotExist:
            request.tenant = None
            raise Http404("Business not found")