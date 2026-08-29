from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
from accounts.models import CustomUser


SHIPPING_CITY = (
    ("feni", "Feni"),
)

SHIPPING_UPAZILLA = (
    ('feni_sadar', "Feni Sadar"),
    ('parshuram', "Parshuram"),
    ('chagalaiya', "Chagalaiya"),
    ('daganbhuiyan', "Daganbhuiyan"),
    ('sonagazi', "Sonagazi"),
    ('fulgazi', "Fulgazi"),
)


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('pending_payment', 'Pending Payment'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='pending_payment',
        db_index=True
    )

    shipping_address = models.TextField(blank=True)
    shipping_city = models.CharField(choices=SHIPPING_CITY, max_length=100, blank=True)
    shipping_upazilla = models.CharField(choices=SHIPPING_UPAZILLA, max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True, default="3900")
    shipping_country = models.CharField(max_length=100, blank=True, default="Bangladesh")
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

    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('sslcommerz', 'SSLCommerz Payment'),
            ('bkash', 'bKash Payment'),
        ],
        default='sslcommerz'
    )
    is_paid = models.BooleanField(default=False)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

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
            import uuid
            self.order_number = f"ORD-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_order_number(self):
        return self.order_number

    def get_gateway_transaction_id(self):
        """Best-effort gateway transaction id from the latest invoice.

        Used to hand a refund processor the id they need for manual
        reconciliation (SSLCommerz val_id / bank_tran_id, bKash trxID).
        """
        invoice = self.invoice_set.order_by('-created_at').first()
        if invoice:
            return (
                invoice.bank_tran_id
                or invoice.val_id
                or invoice.transaction_id
                or ''
            )
        return ''

    def confirm_payment(self):
        from django.db import transaction
        from product.models import ProductVariant
        from cart.models import Cart
        from .order_timeline import OrderTimeline

        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(id=self.id)
            if locked_order.status in ('confirmed', 'failed', 'cancelled'):
                return

            locked_order.is_paid = True
            locked_order.status = 'confirmed'
            locked_order.confirmed_at = timezone.now()
            locked_order.save(update_fields=['is_paid', 'status', 'confirmed_at'])

            self.is_paid = locked_order.is_paid
            self.status = locked_order.status
            self.confirmed_at = locked_order.confirmed_at

            cart = Cart.objects.filter(user=self.user).first()
            if cart:
                cart.items.all().delete()

            for shop_order in self.shop_orders.filter(status='pending'):
                for item in shop_order.items.select_related('product_variant').all():
                    variant = ProductVariant.objects.select_for_update().get(id=item.product_variant_id)
                    variant.stock = models.F('stock') - item.quantity
                    variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                    variant.save(update_fields=['stock', 'reserved_quantity'])

                shop_order.status = 'confirmed'
                shop_order.confirmed_at = timezone.now()
                shop_order.save(update_fields=['status', 'confirmed_at'])

                OrderTimeline.objects.create(
                    shop_order=shop_order,
                    action='confirmed',
                    description='Payment confirmed - stock reserved',
                    created_by=self.user
                )

            # log ledger entry for booking payment (shipping fees)
            from .ledger import FinancialLedgerEntry
            FinancialLedgerEntry.log_booking_payment(
                order=locked_order,
                amount=locked_order.shipping_fee,
                reference_id=locked_order.get_gateway_transaction_id(),
                recorded_by=self.user
            )

    def fail_order(self, reason=None):
        from django.db import transaction
        from product.models import ProductVariant
        from .order_timeline import OrderTimeline

        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(id=self.id)
            if locked_order.status in ['confirmed', 'cancelled', 'failed']:
                return

            locked_order.status = 'failed'
            locked_order.save(update_fields=['status'])
            self.status = locked_order.status

            for shop_order in self.shop_orders.filter(status='pending'):
                for item in shop_order.items.select_related('product_variant').all():
                    variant = ProductVariant.objects.select_for_update().get(id=item.product_variant_id)
                    variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                    variant.save(update_fields=['reserved_quantity'])

                shop_order.status = 'cancelled'
                shop_order.save(update_fields=['status'])

                OrderTimeline.objects.create(
                    shop_order=shop_order,
                    action='cancelled',
                    description=reason or 'Payment failed - reserved stock released',
                )

    def can_be_cancelled(self):
        if self.status == 'pending_payment':
            return True, None

        elif self.status == 'confirmed':
            from datetime import timedelta

            if self.shop_orders.exclude(status__in=['pending', 'confirmed']).exists():
                return False, "Once shop begins processing, cancellation unavailable."

            if not self.confirmed_at:
                return False, "Order confirmation time is missing."

            time_elapsed = timezone.now() - self.confirmed_at
            if time_elapsed > timedelta(minutes=20):
                minutes_elapsed = int(time_elapsed.total_seconds() / 60)
                return False, f"Cancellation window closed. Order was confirmed {minutes_elapsed} minutes ago. You can only cancel within 20 minutes of confirmation."

            return True, None

        else:
            return False, f"Cannot cancel order in '{self.status}' status. Only 'pending_payment' or 'confirmed' orders (within 1 hour) can be cancelled."

    def cancel_order(self, reason=None):
        from django.db import transaction
        from product.models import ProductVariant
        from .order_timeline import OrderTimeline

        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(id=self.id)

            can_cancel, error_reason = locked_order.can_be_cancelled()
            if not can_cancel:
                return False, error_reason

            locked_order.status = 'cancelled'
            locked_order.save(update_fields=['status'])
            self.status = locked_order.status

            for shop_order in locked_order.shop_orders.all():
                if shop_order.status == 'pending':
                    for item in shop_order.items.select_related('product_variant').all():
                        variant = ProductVariant.objects.select_for_update().get(id=item.product_variant_id)
                        variant.reserved_quantity = models.F('reserved_quantity') - item.quantity
                        variant.save(update_fields=['reserved_quantity'])

                    shop_order.status = 'cancelled'
                    shop_order.save(update_fields=['status'])

                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='cancelled',
                        description=reason or 'Order cancelled by customer',
                        created_by=self.user
                    )
                elif shop_order.status == 'confirmed':
                    for item in shop_order.items.select_related('product_variant').all():
                        variant = ProductVariant.objects.select_for_update().get(id=item.product_variant_id)
                        variant.stock = models.F('stock') + item.quantity
                        variant.save(update_fields=['stock'])

                    shop_order.status = 'cancelled'
                    shop_order.save(update_fields=['status'])

                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='cancelled',
                        description=reason or 'Order cancelled by customer',
                        created_by=self.user
                    )

                    # Calculate refund: 95% of shipping fee, 5% processing fee retained
                    from decimal import Decimal
                    refund_amount = (shop_order.shipping_fee * Decimal('0.95')).quantize(Decimal('0.01'))
                    cancellation_charge = shop_order.shipping_fee - refund_amount

                    from .refund_record import RefundRecord
                    RefundRecord.objects.create(
                        order=locked_order,
                        shop_order=shop_order,
                        gateway=RefundRecord._gateway_for(locked_order),
                        gateway_transaction_id=locked_order.get_gateway_transaction_id(),
                        amount=refund_amount,
                        reason=reason or f'Cancelled confirmed (paid) order within 1-hour window (95% refund of shipping fee: TK {refund_amount}, 5% platform fee: TK {cancellation_charge})',
                        created_by=self.user,
                    )

                    # Log ledger entry for refund & platform cancellation fee split
                    from .ledger import FinancialLedgerEntry
                    FinancialLedgerEntry.log_cancellation_refund(
                        order=locked_order,
                        refund_amount=refund_amount,
                        cancellation_charge=cancellation_charge,
                        recorded_by=self.user
                    )

        return True, "Order cancelled successfully"
