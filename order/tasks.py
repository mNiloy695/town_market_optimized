from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from .models import Order



@shared_task
def cancel_expired_pending_orders():
    """
    Cancel orders that have been pending payment beyond configured timeout.
    Releases reserved stock back to available inventory.
    
    This task should be run periodically via Celery Beat.
    """
    timeout_minutes = max(getattr(settings, 'ORDER_PAYMENT_TIMEOUT_MINUTES', 15), 1)
    expiry_cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
    
    expired_orders = Order.objects.filter(
        status='pending_payment',
        created_at__lt=expiry_cutoff,
        is_paid=False
    ).select_related('user')
    
    cancelled_count = 0
    stock_released = 0
    
    for order in expired_orders:
        try:
            with transaction.atomic():
                # Capture releasable quantity before status changes.
                releasable_qty = order.shop_orders.filter(status='pending').aggregate(
                    total=Sum('items__quantity')
                )['total'] or 0

                order.fail_order(
                    reason=f'Order auto-cancelled due to payment timeout ({timeout_minutes} minutes)'
                )
                order.refresh_from_db(fields=['status'])

                if order.status == 'failed':
                    cancelled_count += 1
                    stock_released += releasable_qty
                
        except Exception as e:
            # Log the error but continue with other orders
            print(f"Error cancelling order {order.id}: {str(e)}")
            continue
    
    return {
        'cancelled_orders': cancelled_count,
        'stock_released': stock_released,
        'timeout_minutes': timeout_minutes,
        'message': (
            f'Auto-cancelled {cancelled_count} expired orders '
            f'(timeout: {timeout_minutes} minutes), released {stock_released} items back to inventory'
        ),
    }
