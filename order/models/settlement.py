import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator

class MerchantSettlement(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    settlement_number = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    shop = models.ForeignKey('shop.Shop', on_delete=models.CASCADE, related_name='settlements')
    amount_product = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_shipping = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    transaction_reference = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    recorded_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_settlements'
    )
    shop_orders = models.ManyToManyField('order.ShopOrder', related_name='settlements')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Settlement {self.settlement_number} - {self.shop.name} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.settlement_number:
            self.settlement_number = f"SET-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        self.total_amount = self.amount_product + self.amount_shipping
        super().save(*args, **kwargs)
