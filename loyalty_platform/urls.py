from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    # Business routes
    # Business registration
    path('business/register/', TemplateView.as_view(template_name='accounts/business_register.html'), name='business_register'),
    path('business/', include('tenants.urls')),
    
    # Customer routes
    path('wallet/', TemplateView.as_view(template_name='loyalty/wallet.html'), name='customer_wallet'),
    path('offers/', TemplateView.as_view(template_name='loyalty/offers.html'), name='customer_offers'),
    
    # Home page
    path('', TemplateView.as_view(template_name='shared/home.html'), name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)