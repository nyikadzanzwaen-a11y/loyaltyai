from django.db import models
from django.conf import settings
import uuid

from tenants.models import Business
from loyalty.models import Offer, CustomerWallet


class CustomerSegment(models.Model):
    """Customer segmentation for targeted marketing."""
    SEGMENT_TYPE_CHOICES = [
        ('demographic', 'Demographic'),
        ('behavioral', 'Behavioral'),
        ('value', 'Value-based'),
        ('churn_risk', 'Churn Risk'),
        ('custom', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customer_segments')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    
    # Segment criteria (JSON field would be better but using TextField for simplicity)
    criteria = models.TextField(blank=True, null=True, help_text="JSON representation of segment criteria")
    
    # Segment metrics
    size = models.IntegerField(default=0, help_text="Number of customers in segment")
    avg_spend = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avg_points = models.IntegerField(null=True, blank=True)
    
    is_ai_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business.name} - {self.name}"


class CustomerSegmentMembership(models.Model):
    """Stores which customers belong to which segments."""
    segment = models.ForeignKey(CustomerSegment, on_delete=models.CASCADE, related_name='memberships')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='segments')
    score = models.FloatField(default=1.0, help_text="Membership score/probability (1.0 = 100%)")
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('segment', 'customer')
    
    def __str__(self):
        return f"{self.customer.email} in {self.segment.name}"


class ChurnPrediction(models.Model):
    """Customer churn risk predictions."""
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name='churn_predictions')
    churn_risk_score = models.FloatField(help_text="Probability of churning (0-1)")
    predicted_at = models.DateTimeField(auto_now_add=True)
    
    # Factors influencing prediction
    days_since_last_activity = models.IntegerField(null=True, blank=True)
    engagement_score = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.wallet.customer.email} - {self.wallet.business.name} - {self.churn_risk_score:.2f} risk"


class AIGeneratedOffer(models.Model):
    """AI-generated marketing offers with performance tracking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.OneToOneField(Offer, on_delete=models.CASCADE, related_name='ai_metadata')
    target_segment = models.ForeignKey(CustomerSegment, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_offers')
    
    # Targeting context
    context_factors = models.TextField(blank=True, null=True, help_text="JSON of context factors used for generation")
    
    # Performance metrics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    redemptions = models.IntegerField(default=0)
    
    # A/B testing
    is_test_variant = models.BooleanField(default=False)
    control_variant = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='test_variants')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"AI Offer: {self.offer.title}"

    @property
    def click_through_rate(self):
        """Calculate click-through rate."""
        if self.impressions == 0:
            return 0
        return self.clicks / self.impressions

    @property
    def conversion_rate(self):
        """Calculate conversion rate."""
        if self.clicks == 0:
            return 0
        return self.redemptions / self.clicks


class ChatConversation(models.Model):
    """Customer service chat conversations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_conversations')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='chat_conversations')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"Chat: {self.customer.email} with {self.business.name} on {self.started_at.date()}"


class ChatMessage(models.Model):
    """Individual messages in a chat conversation."""
    MESSAGE_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('ai', 'AI Assistant'),
        ('business', 'Business'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.message_type} message in {self.conversation}"