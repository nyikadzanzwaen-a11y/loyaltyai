from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile for customers only on first creation.

    - Do not create for business admins (is_customer should be False for them).
    - Safe-guards if the flag is missing; defaults to True.
    """
    if not created:
        return

    is_customer = getattr(instance, 'is_customer', True)
    if is_customer:
        UserProfile.objects.get_or_create(user=instance)
