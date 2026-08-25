from django.db import models
from django.core.validators import MinValueValidator
from .order import Order


class MoneyDectedButOrderFailed(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='money_deducted_but_failed')
    reason = models.TextField(blank=True)
    transaction_id = models.CharField(max_length=1000, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    phone = models.CharField(max_length=20, blank=True)
    card_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment failed but money deducted for Order {self.order.order_number}"
