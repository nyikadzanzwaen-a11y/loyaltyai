from django.urls import path, include
from . import views

urlpatterns = [
    path('<slug:slug>/', views.BusinessDashboardView.as_view(), name='business_dashboard'),
    path('<slug:slug>/offers/', views.OfferListView.as_view(), name='business_offers'),
    path('<slug:slug>/customers/', views.CustomerListView.as_view(), name='business_customers'),
    path('<slug:slug>/analytics/', views.BusinessAnalyticsView.as_view(), name='business_analytics'),
    path('<slug:slug>/settings/', views.BusinessSettingsView.as_view(), name='business_settings'),
    
    # Offer management
    path('<slug:slug>/offers/create/', views.CreateOfferView.as_view(), name='create_offer'),
    path('<slug:slug>/offers/<uuid:pk>/edit/', views.UpdateOfferView.as_view(), name='update_offer'),
    path('<slug:slug>/offers/<uuid:pk>/delete/', views.DeleteOfferView.as_view(), name='delete_offer'),
    
    # AI actions
    path('<slug:slug>/ai/generate-offer/', views.GenerateAIOfferView.as_view(), name='generate_ai_offer'),
    path('<slug:slug>/ai/create-segments/', views.create_customer_segments_view, name='create_segments'),
]