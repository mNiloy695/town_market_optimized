from django.db import models
from accounts.models import CustomUser
from .shop_order import ShopOrder


class OrderTimeline(models.Model):
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
