from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'businesses', views.BusinessViewSet)
router.register(r'loyalty-tiers', views.LoyaltyTierViewSet)
router.register(r'offers', views.OfferViewSet)
router.register(r'wallets', views.CustomerWalletViewSet)
router.register(r'transactions', views.WalletTransactionViewSet)
router.register(r'redemptions', views.OfferRedemptionViewSet)
router.register(r'segments', views.CustomerSegmentViewSet)
router.register(r'churn-predictions', views.ChurnPredictionViewSet)
router.register(r'ai-offers', views.AIGeneratedOfferViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]