from rest_framework import viewsets, permissions, status, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.contrib.auth import login as auth_login

from tenants.models import Business, BusinessConfig
from loyalty.models import LoyaltyTier, Offer, CustomerWallet, WalletTransaction, OfferRedemption
from ai_service.models import CustomerSegment, ChurnPrediction, AIGeneratedOffer

from .serializers import (
    UserSerializer, UserRegistrationSerializer,
    BusinessSerializer, BusinessRegistrationSerializer, BusinessConfigSerializer,
    LoyaltyTierSerializer, OfferSerializer, CustomerWalletSerializer,
    WalletTransactionSerializer, OfferRedemptionSerializer,
    CustomerSegmentSerializer, ChurnPredictionSerializer, AIGeneratedOfferSerializer
)
from .permissions import IsBusinessAdmin, IsSuperAdmin, IsOwnerOrAdmin

User = get_user_model()

# User Views
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_business_admin', 'is_customer', 'tenant_id']
    search_fields = ['email', 'first_name', 'last_name']
    
    def get_queryset(self):
        user = self.request.user
        
        # Super admin sees all users
        if user.is_superuser:
            return User.objects.all()
        
        # Business admin sees only users in their tenant
        if user.is_business_admin and user.tenant_id:
            return User.objects.filter(tenant_id=user.tenant_id)
        
        # Regular users see only themselves
        return User.objects.filter(id=user.id)
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        return UserSerializer

# Business Views
class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_verified', 'is_active']
    search_fields = ['name', 'email', 'description']
    
    def get_permissions(self):
        if self.action == 'create' or self.action == 'list' or self.action == 'retrieve':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsBusinessAdmin()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BusinessRegistrationSerializer
        return BusinessSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a business and auto-login the new admin user for a seamless flow."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        business = serializer.save()
        
        # Auto-login the created admin user (session auth)
        email = request.data.get('email')
        if email:
            try:
                admin_user = User.objects.get(email=email)
                auth_login(request, admin_user, backend='django.contrib.auth.backends.ModelBackend')
            except User.DoesNotExist:
                pass
        
        headers = self.get_success_headers(serializer.data)
        return Response({'slug': business.slug}, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def config(self, request, pk=None):
        business = self.get_object()
        config = BusinessConfig.objects.get(business=business)
        serializer = BusinessConfigSerializer(config)
        return Response(serializer.data)
    
    @action(detail=True, methods=['put'], permission_classes=[permissions.IsAuthenticated, IsBusinessAdmin])
    def update_config(self, request, pk=None):
        business = self.get_object()
        config = BusinessConfig.objects.get(business=business)
        serializer = BusinessConfigSerializer(config, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Loyalty Views
class LoyaltyTierViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyTier.objects.all()
    serializer_class = LoyaltyTierSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['business']
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by business if specified in query params
        business_id = self.request.query_params.get('business')
        if business_id:
            return LoyaltyTier.objects.filter(business_id=business_id)
        
        # Business admin sees only their tiers
        if user.is_authenticated and user.is_business_admin and user.tenant_id:
            return LoyaltyTier.objects.filter(business_id=user.tenant_id)
        
        return LoyaltyTier.objects.all()
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsBusinessAdmin()]

class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['business', 'type', 'is_active', 'specific_tier', 'is_ai_generated']
    search_fields = ['title', 'description']
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by business if specified in query params
        business_id = self.request.query_params.get('business')
        if business_id:
            return Offer.objects.filter(business_id=business_id, is_active=True)
        
        # Business admin sees all their offers
        if user.is_authenticated and user.is_business_admin and user.tenant_id:
            return Offer.objects.filter(business_id=user.tenant_id)
        
        # Other users see only active offers
        return Offer.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsBusinessAdmin()]
    
    def perform_create(self, serializer):
        if self.request.user.is_business_admin and self.request.user.tenant_id:
            serializer.save(business_id=self.request.user.tenant_id)

class CustomerWalletViewSet(viewsets.ModelViewSet):
    queryset = CustomerWallet.objects.all()
    serializer_class = CustomerWalletSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['customer', 'business']
    
    def get_queryset(self):
        user = self.request.user
        
        # Super admin sees all wallets
        if user.is_superuser:
            return CustomerWallet.objects.all()
        
        # Business admin sees wallets for their business
        if user.is_business_admin and user.tenant_id:
            return CustomerWallet.objects.filter(business_id=user.tenant_id)
        
        # Regular users see only their own wallets
        return CustomerWallet.objects.filter(customer=user)
    
    @action(detail=True, methods=['post'])
    def add_points(self, request, pk=None):
        wallet = self.get_object()
        points = request.data.get('points', 0)
        description = request.data.get('description', 'Points added')
        transaction_type = request.data.get('transaction_type', 'earn')
        
        if points <= 0:
            return Response({'detail': 'Points must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify permissions
        user = request.user
        if not user.is_superuser and not (user.is_business_admin and user.tenant_id == wallet.business.id):
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            wallet.add_points(points, transaction_type, description)
            return Response({'detail': f'{points} points added successfully'})
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def deduct_points(self, request, pk=None):
        wallet = self.get_object()
        points = request.data.get('points', 0)
        description = request.data.get('description', 'Points deducted')
        transaction_type = request.data.get('transaction_type', 'redeem')
        
        if points <= 0:
            return Response({'detail': 'Points must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify permissions
        user = request.user
        if not user.is_superuser and not (user.is_business_admin and user.tenant_id == wallet.business.id) and user.id != wallet.customer.id:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            wallet.deduct_points(points, transaction_type, description)
            return Response({'detail': f'{points} points deducted successfully'})
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=False, methods=['get'])
    def my_wallets(self, request):
        wallets = CustomerWallet.objects.filter(customer=request.user)
        serializer = self.get_serializer(wallets, many=True)
        return Response(serializer.data)

class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['wallet', 'transaction_type']
    
    def get_queryset(self):
        user = self.request.user
        
        # Super admin sees all transactions
        if user.is_superuser:
            return WalletTransaction.objects.all()
        
        # Business admin sees transactions for their business
        if user.is_business_admin and user.tenant_id:
            return WalletTransaction.objects.filter(wallet__business_id=user.tenant_id)
        
        # Regular users see only their own transactions
        return WalletTransaction.objects.filter(wallet__customer=user)

class OfferRedemptionViewSet(viewsets.ModelViewSet):
    queryset = OfferRedemption.objects.all()
    serializer_class = OfferRedemptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['wallet', 'offer', 'is_used']
    
    def get_queryset(self):
        user = self.request.user
        
        # Super admin sees all redemptions
        if user.is_superuser:
            return OfferRedemption.objects.all()
        
        # Business admin sees redemptions for their business
        if user.is_business_admin and user.tenant_id:
            return OfferRedemption.objects.filter(wallet__business_id=user.tenant_id)
        
        # Regular users see only their own redemptions
        return OfferRedemption.objects.filter(wallet__customer=user)
    
    @action(detail=True, methods=['post'])
    def mark_used(self, request, pk=None):
        redemption = self.get_object()
        redemption.is_used = True
        redemption.used_at = timezone.now()
        redemption.save()
        return Response({'detail': 'Redemption marked as used'})
    
    @action(detail=False, methods=['post'])
    def redeem_offer(self, request):
        offer_id = request.data.get('offer')
        business_id = request.data.get('business')
        
        if not offer_id or not business_id:
            return Response({'detail': 'Offer ID and business ID are required'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            offer = Offer.objects.get(id=offer_id, business_id=business_id)
            wallet = CustomerWallet.objects.get(customer=request.user, business_id=business_id)
            
            # Check if offer is valid
            if not offer.is_valid():
                return Response({'detail': 'This offer is no longer valid'}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Check if enough points
            if wallet.points_balance < offer.points_required:
                return Response({'detail': 'Insufficient points balance'}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Deduct points
            wallet.deduct_points(offer.points_required, 'redeem', f'Redemption of {offer.title}')
            
            # Generate redemption code
            import random, string
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Create redemption record
            redemption = OfferRedemption.objects.create(
                wallet=wallet,
                offer=offer,
                points_used=offer.points_required,
                redemption_code=code
            )
            
            # Update AI metrics if it's an AI offer
            try:
                ai_offer = AIGeneratedOffer.objects.get(offer=offer)
                ai_offer.redemptions += 1
                ai_offer.save()
            except AIGeneratedOffer.DoesNotExist:
                pass
                
            return Response({
                'detail': 'Offer redeemed successfully',
                'redemption_id': redemption.id,
                'code': code
            })
            
        except Offer.DoesNotExist:
            return Response({'detail': 'Offer not found'}, status=status.HTTP_404_NOT_FOUND)
        except CustomerWallet.DoesNotExist:
            return Response({'detail': 'Wallet not found for this business'}, 
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# AI Service Views
class CustomerSegmentViewSet(viewsets.ModelViewSet):
    queryset = CustomerSegment.objects.all()
    serializer_class = CustomerSegmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['business', 'segment_type', 'is_ai_generated']
    
    def get_queryset(self):
        user = self.request.user
        
        # Business admin sees only their segments
        if user.is_business_admin and user.tenant_id:
            return CustomerSegment.objects.filter(business_id=user.tenant_id)
            
        # Super admin sees all
        if user.is_superuser:
            return CustomerSegment.objects.all()
            
        # Not accessible to others
        return CustomerSegment.objects.none()
    
    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsBusinessAdmin()]

class ChurnPredictionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ChurnPrediction.objects.all()
    serializer_class = ChurnPredictionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['wallet__business']
    
    def get_queryset(self):
        user = self.request.user
        
        # Business admin sees only their predictions
        if user.is_business_admin and user.tenant_id:
            return ChurnPrediction.objects.filter(wallet__business_id=user.tenant_id)
            
        # Super admin sees all
        if user.is_superuser:
            return ChurnPrediction.objects.all()
            
        # Not accessible to others
        return ChurnPrediction.objects.none()

class AIGeneratedOfferViewSet(viewsets.ModelViewSet):
    queryset = AIGeneratedOffer.objects.all()
    serializer_class = AIGeneratedOfferSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['offer__business', 'target_segment', 'is_test_variant']
    
    def get_queryset(self):
        user = self.request.user
        
        # Business admin sees only their AI offers
        if user.is_business_admin and user.tenant_id:
            return AIGeneratedOffer.objects.filter(offer__business_id=user.tenant_id)
            
        # Super admin sees all
        if user.is_superuser:
            return AIGeneratedOffer.objects.all()
            
        # Not accessible to others
        return AIGeneratedOffer.objects.none()
    
    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsBusinessAdmin()]