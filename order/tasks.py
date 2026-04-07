from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import Order, ShopOrder, OrderTimeline


@shared_task
def cancel_expired_pending_orders():
    """
    Cancel orders that have been pending payment for more than 1 hour.
    Releases reserved stock back to available inventory.
    
    This task should be run periodically (e.g., every 15 minutes) via Celery Beat.
    """
    # Find orders that are older than 1 hour and still pending payment
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    expired_orders = Order.objects.filter(
        status='pending_payment',
        created_at__lt=one_hour_ago,
        is_paid=False
    ).select_related('user')
    
    cancelled_count = 0
    stock_released = 0
    
    for order in expired_orders:
        try:
            with transaction.atomic():
                # Get all shop orders for this order
                shop_orders = order.shop_orders.filter(status='pending')
                
                for shop_order in shop_orders:
                    # Release reserved stock for each item
                    for item in shop_order.items.all():
                        item.product_variant.reserved_quantity -= item.quantity
                        item.product_variant.save()
                        stock_released += item.quantity
                    
                    # Cancel the shop order
                    shop_order.status = 'cancelled'
                    shop_order.save()
                    
                    # Add timeline entry
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='cancelled',
                        description='Order auto-cancelled due to payment timeout (1 hour)',
                        created_by=None  # System action
                    )
                
                # Update master order status
                order.status = 'cancelled'
                order.save()
                
                cancelled_count += 1
                
        except Exception as e:
            # Log the error but continue with other orders
            print(f"Error cancelling order {order.id}: {str(e)}")
            continue
    
    return {
        'cancelled_orders': cancelled_count,
        'stock_released': stock_released,
        'message': f'Auto-cancelled {cancelled_count} expired orders, released {stock_released} items back to inventory'
    }