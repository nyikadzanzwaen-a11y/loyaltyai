from django.db import models
from django.utils.text import slugify
import uuid

class Business(models.Model):
    """Business model represents a tenant in the platform."""
    CATEGORY_CHOICES = [
        ('retail', 'Retail'),
        ('restaurant', 'Restaurant'),
        ('hospitality', 'Hospitality'),
        ('beauty', 'Beauty & Wellness'),
        ('entertainment', 'Entertainment'),
        ('travel', 'Travel'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Business address fields
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Business settings
    point_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.01, 
                                     help_text="Monetary value of a single point (e.g., 0.01 = 1 cent per point)")
    points_per_currency = models.IntegerField(default=1, 
                                            help_text="Points awarded per unit of currency spent")
    
    # Verification and status
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug_candidate = base_slug
            counter = 1
            # Ensure uniqueness by appending a suffix if needed
            while Business.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
                slug_candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug_candidate
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Business"
        verbose_name_plural = "Businesses"


class BusinessConfig(models.Model):
    """Configuration for a business tenant."""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='config')
    primary_color = models.CharField(max_length=7, default="#007BFF", help_text="Hex code for primary color")
    secondary_color = models.CharField(max_length=7, default="#6C757D", help_text="Hex code for secondary color")
    accent_color = models.CharField(max_length=7, default="#FFC107", help_text="Hex code for accent color")
    
    # Reward settings
    enable_point_expiry = models.BooleanField(default=False)
    point_expiry_days = models.IntegerField(default=365, help_text="Days until points expire")
    enable_cross_business_redemption = models.BooleanField(default=True)
    cross_business_conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1.00,
                                                      help_text="Conversion rate for points from other businesses")
    
    def __str__(self):
        return f"{self.business.name}'s Configuration"