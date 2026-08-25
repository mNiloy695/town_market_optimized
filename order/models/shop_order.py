from django.db import models
from django.core.validators import MinValueValidator
from shop.models import Shop
from .order import Order


class ShopOrder(models.Model):
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

    tracking_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, help_text="Shop's internal notes")
    commission_given = models.BooleanField(default=False)

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
        return f"{self.order.order_number}-{self.shop.id}"

    def save(self, *args, **kwargs):
        if self.total is None:
            self.total = self.subtotal + self.tax + self.shipping_fee - self.discount
        if not self.tracking_number and self.status in ['shipped', 'delivered']:
            import uuid
            self.tracking_number = f"TRK-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)
