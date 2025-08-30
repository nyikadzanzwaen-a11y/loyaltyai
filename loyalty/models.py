from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid

from tenants.models import Business

class LoyaltyTier(models.Model):
    """Loyalty tier for a business."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='loyalty_tiers')
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    minimum_points = models.IntegerField(default=0)
    point_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    
    # Benefits
    special_offers = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    exclusive_events = models.BooleanField(default=False)
    
    # Display
    badge_image = models.ImageField(upload_to='tier_badges/', blank=True, null=True)
    color_code = models.CharField(max_length=7, default="#000000")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['minimum_points']
    
    def __str__(self):
        return f"{self.business.name} - {self.name} Tier"


class Offer(models.Model):
    """Promotional offers created by businesses."""
    TYPE_CHOICES = [
        ('discount', 'Discount'),
        ('points_multiplier', 'Points Multiplier'),
        ('free_item', 'Free Item'),
        ('special_event', 'Special Event'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='offers')
    title = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='discount')
    points_required = models.IntegerField(default=0, help_text="Points required to redeem this offer, 0 if not redeemable with points")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    points_multiplier = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    free_item_description = models.CharField(max_length=255, null=True, blank=True)
    
    # Validity
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Targeting
    specific_tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True, related_name='tier_offers')
    is_ai_generated = models.BooleanField(default=False)
    
    # Media
    image = models.ImageField(upload_to='offer_images/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business.name} - {self.title}"
    
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and 
            self.valid_from <= now and 
            (self.valid_until is None or self.valid_until >= now)
        )


class CustomerWallet(models.Model):
    """Customer wallet for a specific business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallets')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customer_wallets')
    points_balance = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    current_tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    
    # Points expiry tracking
    oldest_active_points = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('customer', 'business')
    
    def __str__(self):
        return f"{self.customer.email} - {self.business.name} Wallet"
    
    def add_points(self, points, transaction_type='earn', description=''):
        """Add points to wallet and create transaction record."""
        self.points_balance += points
        self.lifetime_points += points
        
        if not self.oldest_active_points:
            self.oldest_active_points = timezone.now()
            
        # Update customer tier based on lifetime points
        self._update_tier()
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            points=points,
            transaction_type=transaction_type,
            description=description
        )
        
        self.last_activity = timezone.now()
        self.save()
    
    def deduct_points(self, points, transaction_type='redeem', description=''):
        """Deduct points from wallet and create transaction record."""
        if self.points_balance < points:
            raise ValueError("Insufficient points balance")
        
        self.points_balance -= points
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            points=-points,  # Negative value for deductions
            transaction_type=transaction_type,
            description=description
        )
        
        self.last_activity = timezone.now()
        self.save()
    
    def _update_tier(self):
        """Update customer tier based on lifetime points."""
        tiers = self.business.loyalty_tiers.all().order_by('-minimum_points')
        for tier in tiers:
            if self.lifetime_points >= tier.minimum_points:
                self.current_tier = tier
                break


class WalletTransaction(models.Model):
    """Transaction records for customer wallets."""
    TRANSACTION_TYPES = [
        ('earn', 'Earn Points'),
        ('redeem', 'Redeem Points'),
        ('expire', 'Points Expired'),
        ('transfer', 'Points Transfer'),
        ('bonus', 'Bonus Points'),
        ('adjustment', 'Manual Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name='transactions')
    points = models.IntegerField()  # Positive for additions, negative for deductions
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True, null=True)  # For external reference IDs
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.points > 0:
            return f"{self.wallet.customer.email} earned {self.points} points at {self.wallet.business.name}"
        else:
            return f"{self.wallet.customer.email} redeemed {abs(self.points)} points at {self.wallet.business.name}"
    
    class Meta:
        ordering = ['-created_at']


class OfferRedemption(models.Model):
    """Record of offer redemptions by customers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name='offer_redemptions')
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='redemptions')
    redeemed_at = models.DateTimeField(auto_now_add=True)
    points_used = models.IntegerField(default=0)
    redemption_code = models.CharField(max_length=50, blank=True, null=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.wallet.customer.email} redeemed {self.offer.title}"