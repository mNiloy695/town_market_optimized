import uuid
from django.db import models
from django.utils import timezone


class CommissionPayment(models.Model):
    """Merchant -> Platform commission payment.

    Directionally opposite of MerchantSettlement (Platform -> Merchant payout).
    A positive per-order commission liability arises when the merchant owes the
    platform more (platform_commission) than the platform holds for them
    (shipping_fee). Payments against that liability are recorded here and never
    touch ShopOrder.settlement_status, which only tracks Platform -> Merchant
    payouts.
    """

    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
    ]

    payment_number = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    shop = models.ForeignKey('shop.Shop', on_delete=models.CASCADE, related_name='commission_payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    liability_before = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    liability_after = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=50, default='manual')
    transaction_reference = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received', db_index=True)
    # When True, an amount above the current liability is accepted; the excess
    # is stored on `overpaid_amount` as a merchant credit against future commission.
    overpay_credit = models.BooleanField(default=False)
    overpaid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    shop_orders = models.ManyToManyField('order.ShopOrder', related_name='commission_payments')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    recorded_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_commission_payments'
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'transaction_reference'],
                name='unique_commission_payment_ref_per_shop'
            )
        ]

    def __str__(self):
        return f"CommissionPayment {self.payment_number} - {self.shop.name} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = f"CMP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class CommissionPaymentLine(models.Model):
    """Explicit allocation of a CommissionPayment against one shop order.

    The authoritative, provable record of how much of each payment offset which
    order (FIFO allocation). The CommissionPayment -> shop_orders M2M is kept
    for legacy records that predate line-level tracking.
    """

    payment = models.ForeignKey(
        'order.CommissionPayment', on_delete=models.CASCADE, related_name='lines'
    )
    shop_order = models.ForeignKey(
        'order.ShopOrder', on_delete=models.CASCADE, related_name='commission_payment_lines'
    )
    shop = models.ForeignKey(
        'shop.Shop', on_delete=models.CASCADE, related_name='commission_payment_lines'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Order in which the allocation was applied (FIFO sequence for audit).
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sequence', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['payment', 'shop_order'],
                name='unique_commission_payment_line_per_order'
            )
        ]

    def __str__(self):
        return f"{self.payment.payment_number} -> {self.shop_order.get_order_number()}: TK {self.amount}"