from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

from order.models.order import Order
from order.models.shop_order import ShopOrder


class RefundRecord(models.Model):
    """
    A refund that must be completed MANUALLY (manual reconciliation model).

    Never auto-executed: gateway refunds (SSLCommerz / bKash) are initiated by
    an operator from Django admin using the stored gateway transaction ID.
    """

    class Gateway(models.TextChoices):
        SSLCOMMERZ = 'sslcommerz', 'SSLCommerz'
        BKASH = 'bkash', 'bKash'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        DECLINED = 'declined', 'Declined'
        PROCESSED = 'processed', 'Processed'

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='refund_records'
    )
    shop_order = models.ForeignKey(
        ShopOrder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='refund_records',
    )
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    gateway_transaction_id = models.CharField(max_length=1000, blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_records_created',
    )
    resolved_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_records_resolved',
    )
    reviewed_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_reviews',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_payouts',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payout_reference = models.CharField(max_length=255, blank=True, default='')
    admin_notes = models.TextField(blank=True, default='')
    customer_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['order', '-created_at']),
        ]

    def __str__(self):
        return f"Refund {self.gateway} {self.amount} for order {self.order.order_number}"

    @classmethod
    def create_for_order(cls, order, amount=None, reason='', user=None):
        """Record a manual-reconciliation refund for a whole (paid) order."""
        amount = amount if amount is not None else order.total_amount
        return cls.objects.create(
            order=order,
            gateway=cls._gateway_for(order),
            gateway_transaction_id=order.get_gateway_transaction_id(),
            amount=amount,
            reason=reason,
            created_by=user,
        )

    @classmethod
    def create_for_shop_order(cls, shop_order, reason='', user=None):
        """Record a manual-reconciliation refund for one paid shop order."""
        return cls.objects.create(
            order=shop_order.order,
            shop_order=shop_order,
            gateway=cls._gateway_for(shop_order.order),
            gateway_transaction_id=shop_order.order.get_gateway_transaction_id(),
            amount=shop_order.total,
            reason=reason,
            created_by=user,
        )

    @staticmethod
    def _gateway_for(order):
        if order.payment_method == 'bkash':
            return RefundRecord.Gateway.BKASH
        return RefundRecord.Gateway.SSLCOMMERZ