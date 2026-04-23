from django.template.defaultfilters import default
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
from accounts.models import CustomUser
from shop.models import Shop
from product.models import ProductVariant


SHIPPING_CITY=(
    ("feni","Feni"),
)

SHIPPING_UPAZILLA=(
    ('feni_sadar',"Feni Sadar"),
    ('parshuram',"Parshuram"),
    ('chagalaiya',"Chagalaiya"),
    ('daganbhuiyan',"Daganbhuiyan"),
    ('sonagazi',"Sonagazi"),
    ('fulgazi',"Fulgazi"),
    
)
class Order(models.Model):
    """
    Master order model for a customer.
    Each order represents a transaction from a customer.
    """
    ORDER_STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('pending_payment', 'Pending Payment'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True, db_index=True,blank=True)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20, 
        choices=ORDER_STATUS_CHOICES, 
        default='pending_payment',
        db_index=True
    )
    
    # Delivery information
    shipping_address = models.TextField(blank=True)
    shipping_city = models.CharField(choices=SHIPPING_CITY,max_length=100, blank=True)
    shipping_upazilla = models.CharField(choices=SHIPPING_UPAZILLA,max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True,default="3900")
    shipping_country = models.CharField(max_length=100, blank=True,default="Bangladesh")
    phone_number = models.CharField(
        max_length=20, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^(?:\+88|88)?(01[3-9]\d{8})$",
                message="Please provide a valid Bangladeshi mobile number."
            )
        ]
    )
    
    # Payment tracking
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('sslcommerz', 'SSLCommerz Payment'),
        ],
        default='sslcommerz'
    )
    is_paid = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # When payment was confirmed
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.user.phone}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate unique order number
            import uuid
            self.order_number = f"ORD-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_order_number(self):
        return self.order_number
    
    def confirm_payment(self):
        """
        Confirm payment and reduce actual stock from reserved stock.
        Call this after payment is successfully processed.
        """
        from django.db import transaction
        
        with transaction.atomic():
            self.is_paid = True
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()

            # Clear user's cart upon successful payment
            from cart.models import Cart
            cart = Cart.objects.filter(user=self.user).first()
            if cart:
                cart.items.all().delete()
            
            # For each shop order, reduce actual stock
            for shop_order in self.shop_orders.filter(status='pending'):
                for item in shop_order.items.select_related('product_variant').all():
                    # Reduce actual stock and reserved quantity atomically
                    variant = item.product_variant
                    variant.stock = models.F('stock') - item.quantity
                    variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                    variant.save(update_fields=['stock', 'reserved_quantity'])
                
                # Update shop order status to confirmed
                shop_order.status = 'confirmed'
                shop_order.confirmed_at = timezone.now()
                shop_order.save(update_fields=['status', 'confirmed_at'])
                
                # Add timeline entry
                from .models import OrderTimeline
                OrderTimeline.objects.create(
                    shop_order=shop_order,
                    action='confirmed',
                    description='Payment confirmed - stock reserved',
                    created_by=self.user
                )

    def fail_order(self, reason=None):
        """
        Handle payment failure and release reserved stock immediately.
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Only process if not already finalized
            if self.status not in ['confirmed', 'cancelled', 'failed']:
                self.status = 'failed'
                self.save()
                
                # Release reserved stock for all associated shop orders
                for shop_order in self.shop_orders.filter(status='pending'):
                    # Use select_related and bulk-like updates where possible
                    for item in shop_order.items.select_related('product_variant').all():
                        variant = item.product_variant
                        variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                        variant.save(update_fields=['reserved_quantity'])
                    
                    shop_order.status = 'cancelled'
                    shop_order.save(update_fields=['status'])
                    
                    # Log to timeline
                    from .models import OrderTimeline
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='cancelled',
                        description=reason or 'Payment failed - reserved stock released',
                    )
    
    def can_be_cancelled(self):
        """
        Check if the master order can be cancelled.
        Returns: (can_cancel: bool, reason: str or None)
        
        Rules:
        - pending_payment: Can always be cancelled (before payment)
        - confirmed: Cannot be cancelled
        - Other statuses: Cannot be cancelled
        """
        if self.status == 'pending_payment':
            return True, None
        
        elif self.status == 'confirmed':
            return False, "Confirmed orders cannot be cancelled."
        
        else:
            return False, f"Cannot cancel order in '{self.status}' status. Only 'pending_payment' orders can be cancelled."
    
    def cancel_order(self, reason=None):
        """
        Cancel the master order and all related shop orders.
        Releases reserved stock for cancellable order items.
        Returns: (success: bool, message: str)
        """
        from django.db import transaction
        
        # Check if cancellation is allowed
        can_cancel, error_reason = self.can_be_cancelled()
        if not can_cancel:
            return False, error_reason
        
        with transaction.atomic():
            # Cancel the master order
            self.status = 'cancelled'
            self.save(update_fields=['status'])
            
            # Cancel all related shop orders and release stock
            for shop_order in self.shop_orders.all():
                if shop_order.status in ['pending', 'confirmed']:
                    # Release reserved stock for each item
                    for item in shop_order.items.select_related('product_variant').all():
                        variant = item.product_variant
                        variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                        variant.save(update_fields=['reserved_quantity'])
                    
                    # Mark shop order as cancelled
                    shop_order.status = 'cancelled'
                    shop_order.save(update_fields=['status'])
                    
                    # Log to timeline
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='cancelled',
                        description=reason or 'Order cancelled by customer',
                        created_by=self.user
                    )
        
        return True, "Order cancelled successfully"


class ShopOrder(models.Model):
    """
    Individual shop order created from a master order.
    One master order can have multiple ShopOrders (one per shop).
    Used to allow vendors to see and manage only their orders.
    """
    SHOP_ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned', 'Returned'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='shop_orders')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    
    # Order details
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    shipping_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    
    status = models.CharField(
        max_length=20,
        choices=SHOP_ORDER_STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Tracking
    tracking_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, help_text=f'Shop\'s internal notes')
    commission_given = models.BooleanField(default=False)  # Track if commission has been given by the shop owner to the platform  
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        unique_together = ('order', 'shop')

    def __str__(self):
        return f"Shop Order {self.id} - {self.shop.name} - {self.status}"
    
    def get_order_number(self):
        """Return formatted order number for shop"""
        return f"{self.order.order_number}-{self.shop.id}"
    
    def save(self, *args, **kwargs):
        # Ensure total is calculated correctly
        if not self.total:
            self.total = self.subtotal + self.tax + self.shipping_fee - self.discount
        if not self.tracking_number and self.status in ['shipped', 'delivered']:
            # Generate tracking number if not provided
            import uuid
            self.tracking_number = f"TRK-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    """
    Individual items within a shop order.
    Tracks product variant quantity and price at time of purchase.
    """

    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name='order_items'
    )
    
    # Store price at purchase time (price may change later)
    price_at_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    
    # Line total
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    
    # Status tracking
    ITEM_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=ITEM_STATUS_CHOICES,
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.quantity}x {self.product_variant.product.name} in ShopOrder {self.shop_order.id}"
    
    def save(self, *args, **kwargs):
        if not self.price_at_purchase:
            self.price_at_purchase = self.product_variant.price
        self.line_total = self.price_at_purchase * self.quantity
        super().save(*args, **kwargs)


class OrderTimeline(models.Model):
    """
    Track all status changes for transparency.
    Useful for audit trails and customer communication.
    """
    TIMELINE_ACTIONS = [
        ('created', 'Order Created'),
        ('confirmed', 'Order Confirmed'),
        ('processing', 'Processing Started'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('payment_processed', 'Payment Processed'),
        ('return_requested', 'Return Requested'),
        ('returned', 'Item Returned'),
    ]
    
    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='timeline')
    action = models.CharField(max_length=50, choices=TIMELINE_ACTIONS)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.shop_order.id}"
