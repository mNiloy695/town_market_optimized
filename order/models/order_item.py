from django.db import models
from django.core.validators import MinValueValidator
from product.models import ProductVariant
from .shop_order import ShopOrder


class OrderItem(models.Model):
    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name='order_items'
    )

    price_at_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

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
