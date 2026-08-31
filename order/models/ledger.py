import uuid
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

class FinancialLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        DEBIT = 'debit', 'Debit'
        CREDIT = 'credit', 'Credit'

    class Category(models.TextChoices):
        CUSTOMER_PAYMENT = 'customer_payment', 'Customer Payment'
        PLATFORM_COMMISSION = 'platform_commission', 'Platform Commission'
        MERCHANT_PRODUCT_EARNING = 'merchant_product_earning', 'Merchant Product Earning'
        SHIPPING_COLLECTED = 'shipping_collected', 'Shipping Collected'
        CUSTOMER_REFUND = 'customer_refund', 'Customer Refund'
        MERCHANT_SETTLEMENT = 'merchant_settlement', 'Merchant Settlement'
        COMMISSION_PAYMENT = 'commission_payment', 'Commission Payment'
        CANCELLATION_CHARGE = 'cancellation_charge', 'Cancellation Charge'
        COD_COLLECTED = 'cod_collected', 'COD Collected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    category = models.CharField(max_length=30, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))]
    )
    order = models.ForeignKey(
        'order.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries'
    )
    shop_order = models.ForeignKey(
        'order.ShopOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries'
    )
    shop = models.ForeignKey(
        'shop.Shop', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries'
    )
    reference_id = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recorded_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_ledger_entries'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['shop', '-created_at']),
        ]

    def __str__(self):
        return f"{self.category.upper()} | {self.entry_type.upper()} | TK {self.amount} | Shop: {self.shop_id or 'Platform'}"

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Ledger entries are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ledger entries are immutable and cannot be deleted.")

    @classmethod
    def log_booking_payment(cls, order, amount, reference_id='', recorded_by=None):
        """Log the initial online booking payment (shipping fees)."""
        # Debit: Cash/Asset (Platform holds cash)
        cls.objects.create(
            entry_type=cls.EntryType.DEBIT,
            category=cls.Category.CUSTOMER_PAYMENT,
            amount=amount,
            order=order,
            reference_id=reference_id,
            notes=f"Online payment of shipping fees for order {order.order_number}",
            recorded_by=recorded_by
        )
        # Credit: Shipping Liability (Platform owes shipping to the merchants)
        for shop_order in order.shop_orders.all():
            cls.objects.create(
                entry_type=cls.EntryType.CREDIT,
                category=cls.Category.SHIPPING_COLLECTED,
                amount=shop_order.shipping_fee,
                order=order,
                shop_order=shop_order,
                shop=shop_order.shop,
                reference_id=reference_id,
                notes=f"Shipping fee liability recorded for shop {shop_order.shop.name}",
                recorded_by=recorded_by
            )

    @classmethod
    def log_cancellation_refund(cls, order, refund_amount, cancellation_charge, recorded_by=None):
        """Log early cancellation within 1-hour window (95% refund, 5% fee)."""
        # Debit: Shipping Liability (Reduce platform liability)
        for shop_order in order.shop_orders.all():
            cls.objects.create(
                entry_type=cls.EntryType.DEBIT,
                category=cls.Category.SHIPPING_COLLECTED,
                amount=shop_order.shipping_fee,
                order=order,
                shop_order=shop_order,
                shop=shop_order.shop,
                notes=f"Reversed shipping fee liability for shop {shop_order.shop.name} due to cancellation",
                recorded_by=recorded_by
            )
        # Credit: Cash/Asset (Outflow of 95% of shipping fee to customer)
        if refund_amount > 0:
            cls.objects.create(
                entry_type=cls.EntryType.CREDIT,
                category=cls.Category.CUSTOMER_REFUND,
                amount=refund_amount,
                order=order,
                notes=f"95% refund of booking/shipping fee to customer for order {order.order_number}",
                recorded_by=recorded_by
            )
        # Credit: Platform Revenue (5% cancellation fee kept by platform)
        if cancellation_charge > 0:
            cls.objects.create(
                entry_type=cls.EntryType.CREDIT,
                category=cls.Category.CANCELLATION_CHARGE,
                amount=cancellation_charge,
                order=order,
                notes=f"5% platform cancellation processing fee for order {order.order_number}",
                recorded_by=recorded_by
            )

    @classmethod
    def log_cod_delivery(cls, shop_order, recorded_by=None):
        """Log cash collection and platform commission splits at delivery."""
        # 1. Log COD Cash Collected by Merchant
        cls.objects.create(
            entry_type=cls.EntryType.DEBIT,
            category=cls.Category.COD_COLLECTED,
            amount=shop_order.cod_amount,
            order=shop_order.order,
            shop_order=shop_order,
            shop=shop_order.shop,
            notes=f"Merchant collected Cash on Delivery of TK {shop_order.cod_amount} for sub-order {shop_order.id}",
            recorded_by=recorded_by
        )
        # 2. Log Platform Commission Revenue (Credit)
        cls.objects.create(
            entry_type=cls.EntryType.CREDIT,
            category=cls.Category.PLATFORM_COMMISSION,
            amount=shop_order.platform_commission,
            order=shop_order.order,
            shop_order=shop_order,
            shop=shop_order.shop,
            notes=f"Platform commission of {shop_order.commission_percentage * 100}% recorded: TK {shop_order.platform_commission}",
            recorded_by=recorded_by
        )
        # 3. Log Merchant Product Earning (Credit to merchant receivable liability)
        cls.objects.create(
            entry_type=cls.EntryType.CREDIT,
            category=cls.Category.MERCHANT_PRODUCT_EARNING,
            amount=shop_order.merchant_net,
            order=shop_order.order,
            shop_order=shop_order,
            shop=shop_order.shop,
            notes=f"Merchant net product earning recorded: TK {shop_order.merchant_net}",
            recorded_by=recorded_by
        )

    @classmethod
    def log_commission_payment(cls, payment, recorded_by=None):
        """Log a Merchant -> Platform commission payment received by the platform.

        A single DEBIT entry encodes cash flowing in to the platform while
        reducing the merchant's commission liability. The notes preserve the
        audit trail of which order numbers were offset (FIFO allocation).
        """
        lines = list(payment.lines.select_related('shop_order__order').all())
        if lines:
            order_numbers = [
                (f"{line.shop_order.get_order_number()} x{line.amount}")
                for line in lines
            ]
        else:  # Legacy write linked via M2M before line-level tracking.
            order_numbers = [so.get_order_number() for so in payment.shop_orders.all()]
        order_numbers = order_numbers or ['(unallocated)']
        cls.objects.create(
            entry_type=cls.EntryType.DEBIT,
            category=cls.Category.COMMISSION_PAYMENT,
            amount=payment.amount,
            shop=payment.shop,
            reference_id=payment.transaction_reference,
            notes=(
                f"Commission payment {payment.payment_number} received from {payment.shop.name}: "
                f"TK {payment.amount} (liability {payment.liability_before} -> {payment.liability_after}) "
                f"applied to {', '.join(order_numbers)}"
            ),
            recorded_by=recorded_by
        )

    @classmethod
    def log_settlement(cls, settlement, recorded_by=None):
        """Log the net payout settlement execution to a merchant."""
        # Debit: Merchant Liabilities (Product earning settled, shipping settled)
        if settlement.amount_product < 0 or settlement.amount_shipping < 0:
            raise ValueError(
                "Cannot log a settlement with negative amounts. "
                "A merchant commission debt must be recorded as a CommissionPayment, "
                "not as a negative MerchantSettlement payout."
            )
        if settlement.amount_product > 0:
            cls.objects.create(
                entry_type=cls.EntryType.DEBIT,
                category=cls.Category.MERCHANT_SETTLEMENT,
                amount=settlement.amount_product,
                shop=settlement.shop,
                reference_id=settlement.transaction_reference,
                notes=f"Product earnings payout settled to merchant in batch {settlement.settlement_number}",
                recorded_by=recorded_by
            )
        if settlement.amount_shipping > 0:
            cls.objects.create(
                entry_type=cls.EntryType.DEBIT,
                category=cls.Category.MERCHANT_SETTLEMENT,
                amount=settlement.amount_shipping,
                shop=settlement.shop,
                reference_id=settlement.transaction_reference,
                notes=f"Shipping fees payout settled to merchant in batch {settlement.settlement_number}",
                recorded_by=recorded_by
            )
