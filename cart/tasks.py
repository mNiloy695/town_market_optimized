from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import CartItem

@shared_task
def release_expired_cart_stock():
    """
    Remove cart items that haven't been updated in 30 minutes.
    Cart actions do not reserve stock anymore.
    """
    expiration_time = timezone.now() - timedelta(minutes=30)
    expired_items = CartItem.objects.filter(updated_at__lt=expiration_time)
    expired_count = expired_items.count()
    expired_items.delete()
    return f"Deleted {expired_count} expired cart items."
