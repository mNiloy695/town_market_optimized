from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction, models
from .models import CartItem

@shared_task
def release_expired_cart_stock():
    """
    Release stock for cart items that haven't been updated in 30 minutes.
    """
    expiration_time = timezone.now() - timedelta(minutes=30)
    expired_items = CartItem.objects.filter(updated_at__lt=expiration_time).select_related('product_variant')
    
    released_count = 0
    
    for item in expired_items:
        try:
            with transaction.atomic():
                variant = item.product_variant
                # Release reserved stock
                variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                variant.save(update_fields=['reserved_quantity'])
                
                # Delete the expired cart item
                item.delete()
                released_count += 1
        except Exception as e:
            print(f"Error releasing stock for CartItem {item.id}: {str(e)}")
            continue
            
    return f"Released stock for {released_count} expired cart items."
