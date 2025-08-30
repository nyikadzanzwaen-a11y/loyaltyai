from rest_framework import serializers
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from tenants.models import Business, BusinessConfig
from loyalty.models import LoyaltyTier, Offer, CustomerWallet, WalletTransaction, OfferRedemption
from ai_service.models import CustomerSegment, ChurnPrediction, AIGeneratedOffer

User = get_user_model()

# User Serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_business_admin', 'is_customer', 'phone']
        read_only_fields = ['id']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'phone']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        email = validated_data.get('email')
        if email:
            validated_data['username'] = email
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

# Business Serializers
class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'slug', 'email', 'phone', 'category', 'description', 
                  'logo', 'website', 'address', 'city', 'state', 'country', 
                  'postal_code', 'point_value', 'points_per_currency', 
                  'is_verified', 'is_active', 'created_at']
        read_only_fields = ['id', 'slug', 'is_verified', 'created_at']

class BusinessRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=False)
    terms = serializers.BooleanField(write_only=True, required=False)
    enable_cross_business = serializers.BooleanField(write_only=True, required=False, default=True)
    
    class Meta:
        model = Business
        fields = [
            'name', 'email', 'password', 'confirm_password', 'terms',
            'category', 'description', 'logo', 'phone', 'website',
            'address', 'city', 'state', 'country', 'postal_code',
            'points_per_currency', 'point_value', 'enable_cross_business', 'slug'
        ]
        read_only_fields = ['slug']

    def validate_email(self, value):
        value = value.strip()
        # Ensure the email is unique across both Business and User
        if Business.objects.filter(email__iexact=value).exists() or User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists')
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        confirm = attrs.get('confirm_password')
        if confirm is not None and password != confirm:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        # Remove non-model fields
        validated_data.pop('confirm_password', None)
        email = validated_data.pop('email')
        enable_cross = validated_data.pop('enable_cross_business', True)
        validated_data.pop('terms', None)
        
        # Create business
        try:
            business = Business.objects.create(email=email, **validated_data)
        except IntegrityError:
            raise serializers.ValidationError({'email': 'A business with this email already exists'})
        
        # Create admin user
        try:
            admin_user = User.objects.create_user(
                email=email,
                password=password,
                tenant_id=business.id,
                is_business_admin=True,
                is_customer=False,
                username=email
            )
        except IntegrityError:
            # Roll back business if user creation fails due to unique email
            business.delete()
            raise serializers.ValidationError({'email': 'A user with this email already exists'})
        
        # Create default business config
        config = BusinessConfig.objects.create(business=business)
        # Apply cross-business redemption setting if provided
        try:
            config.enable_cross_business_redemption = bool(enable_cross)
            config.save()
        except Exception:
            pass
        
        # Create default loyalty tier
        LoyaltyTier.objects.create(
            business=business,
            name='Standard',
            description='Default membership tier',
            minimum_points=0
        )
        
        return business

class BusinessConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessConfig
        fields = ['primary_color', 'secondary_color', 'accent_color', 
                  'enable_point_expiry', 'point_expiry_days', 
                  'enable_cross_business_redemption', 'cross_business_conversion_rate']

# Loyalty Serializers
class LoyaltyTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTier
        fields = ['id', 'name', 'description', 'minimum_points', 'point_multiplier', 
                  'special_offers', 'priority_support', 'exclusive_events', 
                  'badge_image', 'color_code']

class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = ['id', 'title', 'description', 'type', 'points_required', 
                  'discount_percentage', 'discount_amount', 'points_multiplier', 
                  'free_item_description', 'is_active', 'valid_from', 'valid_until', 
                  'specific_tier', 'is_ai_generated', 'image', 'created_at']
        read_only_fields = ['id', 'is_ai_generated', 'created_at']

class CustomerWalletSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    tier_name = serializers.CharField(source='current_tier.name', read_only=True)
    
    class Meta:
        model = CustomerWallet
        fields = ['id', 'customer', 'business', 'business_name', 'points_balance', 
                  'lifetime_points', 'current_tier', 'tier_name', 'created_at', 'last_activity']
        read_only_fields = ['id', 'customer', 'points_balance', 'lifetime_points', 
                            'current_tier', 'created_at', 'last_activity']

class WalletTransactionSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='wallet.business.name', read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = ['id', 'wallet', 'business_name', 'points', 'transaction_type', 
                  'description', 'reference', 'created_at']
        read_only_fields = ['id', 'created_at']

class OfferRedemptionSerializer(serializers.ModelSerializer):
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    business_name = serializers.CharField(source='wallet.business.name', read_only=True)
    
    class Meta:
        model = OfferRedemption
        fields = ['id', 'wallet', 'offer', 'offer_title', 'business_name', 'redeemed_at', 
                  'points_used', 'redemption_code', 'is_used', 'used_at']
        read_only_fields = ['id', 'redeemed_at', 'redemption_code']

# AI Service Serializers
class CustomerSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerSegment
        fields = ['id', 'name', 'description', 'segment_type', 'criteria', 
                  'size', 'avg_spend', 'avg_points', 'is_ai_generated', 'created_at']
        read_only_fields = ['id', 'size', 'avg_spend', 'avg_points', 'created_at']

class ChurnPredictionSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='wallet.customer.email', read_only=True)
    business_name = serializers.CharField(source='wallet.business.name', read_only=True)
    
    class Meta:
        model = ChurnPrediction
        fields = ['id', 'wallet', 'customer_email', 'business_name', 
                  'churn_risk_score', 'predicted_at', 'days_since_last_activity', 'engagement_score']
        read_only_fields = ['id', 'predicted_at']

class AIGeneratedOfferSerializer(serializers.ModelSerializer):
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    
    class Meta:
        model = AIGeneratedOffer
        fields = ['id', 'offer', 'offer_title', 'target_segment', 
                  'context_factors', 'impressions', 'clicks', 'redemptions', 
                  'is_test_variant', 'control_variant', 'created_at', 
                  'click_through_rate', 'conversion_rate']
        read_only_fields = ['id', 'impressions', 'clicks', 'redemptions', 
                           'created_at', 'click_through_rate', 'conversion_rate']