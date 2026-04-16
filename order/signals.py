"""
Signals for Order app.

Handles:
- Order creation notifications
- Inventory management
- Payment processing events
- Vendor notifications
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import ShopOrder, OrderItem, OrderTimeline,Order
from accounts.models import CustomUser
from invoice.models import Invoice


@receiver(post_save,sender=Order)
def handle_invoice_creation_based_on_order(sender,instance,created,**kwargs):
    if created:
        Invoice.objects.create(
            order=instance,
            invoice_number=instance.get_order_number(),
            transaction_id=instance.order_number,
            amount=instance.total_amount,
            invoice_date=instance.created_at,
            payment_method=instance.payment_method or "sslcommerz",
            customer_name=instance.user.name or instance.phone_number,
            customer_email=instance.user.email or instance.user.phone or instance.phone_number,
            customer_phone=instance.user.phone or instance.phone_number,
        )

@receiver(post_save, sender=ShopOrder)
def handle_shop_order_creation(sender, instance, created, **kwargs):
    """
    Handle new shop order creation.
    - Create initial timeline entry
    - Send email to vendor
    """
    if created:
        # Timeline entry already created in view, but can add more here if needed
        send_vendor_order_notification(instance)


@receiver(post_save, sender=ShopOrder)
def handle_shop_order_status_change(sender, instance, created, update_fields, **kwargs):
    """
    Handle shop order status changes.
    - Send notifications to customer and vendor
    """
    if not created and update_fields and 'status' in update_fields:
        # Send status change notifications
        send_customer_status_notification(instance)
        send_vendor_status_notification(instance)


def send_vendor_order_notification(shop_order):
    """Send email notification to vendor when new order arrives"""
    try:
        vendor = shop_order.shop.owner
        context = {
            'vendor_name': vendor.name,
            'order_id': shop_order.get_order_number(),
            'customer_name': shop_order.order.user.name,
            'total_amount': shop_order.total,
            'item_count': shop_order.items.count(),
        }
        
        # In production, use actual email templates
        subject = f"New Order {shop_order.get_order_number()} - {shop_order.shop.name}"
        # html_message = render_to_string('order/vendor_new_order.html', context)
        
        # For now, simple text email
        message = f"""
        Hello {vendor.name},
        
        You have received a new order {shop_order.get_order_number()}.
        
        Customer: {shop_order.order.user.name}
        Items: {shop_order.items.count()}
        Total: {shop_order.total}
        
        Please log in to your dashboard to confirm and manage this order.
        """
        
        # Uncomment in production
        # send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [vendor.email])
    except Exception as e:
        print(f"Error sending vendor notification: {str(e)}")


def send_customer_status_notification(shop_order):
    """Send email notification to customer about order status"""
    try:
        customer = shop_order.order.user
        
        status_messages = {
            'pending': 'Your order has been received and is awaiting confirmation.',
            'confirmed': 'Your order has been confirmed by the vendor.',
            'processing': 'Your order is being processed.',
            'shipped': f'Your order has been shipped. Tracking: {shop_order.tracking_number}',
            'delivered': 'Your order has been delivered.',
            'cancelled': 'Your order has been cancelled.',
        }
        
        message = status_messages.get(shop_order.status, 'Order status updated')
        
        subject = f"Order {shop_order.get_order_number()} - {shop_order.status.title()}"
        full_message = f"""
        Hello {customer.name},
        
        {message}
        
        Order: {shop_order.get_order_number()}
        Shop: {shop_order.shop.name}
        
        Track your order in the app.
        """
        
        # Uncomment in production
        # send_mail(subject, full_message, settings.DEFAULT_FROM_EMAIL, [customer.email])
    except Exception as e:
        print(f"Error sending customer notification: {str(e)}")


def send_vendor_status_notification(shop_order):
    """Send email notification to vendor about important status changes"""
    try:
        vendor = shop_order.shop.owner
        
        important_statuses = ['delivered', 'cancelled', 'return_requested']
        
        if shop_order.status not in important_statuses:
            return
        
        subject = f"Order {shop_order.get_order_number()} - {shop_order.status.title()}"
        message = f"""
        Order {shop_order.get_order_number()} status: {shop_order.status}
        
        Customer: {shop_order.order.user.name}
        Items: {shop_order.items.count()}
        
        Please take necessary action in your dashboard.
        """
        
        # Uncomment in production
        # send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [vendor.email])
    except Exception as e:
        print(f"Error sending vendor status notification: {str(e)}")


# celery task for automated order processing (advanced feature)
# from celery import shared_task
# @shared_task
# def auto_confirm_pending_orders():
#     """Auto-confirm orders after 30 minutes if not manually confirmed"""
#     from datetime import timedelta
#     from django.utils import timezone
#     
#     thirty_mins_ago = timezone.now() - timedelta(minutes=30)
#     pending_orders = ShopOrder.objects.filter(
#         status='pending',
#         created_at__lt=thirty_mins_ago
#     )
#     
#     for order in pending_orders:
#         order.status = 'confirmed'
#         order.confirmed_at = timezone.now()
#         order.save()
#         
#         OrderTimeline.objects.create(
#             shop_order=order,
#             action='confirmed',
#             description='Auto-confirmed after 30 minutes'
#         )



