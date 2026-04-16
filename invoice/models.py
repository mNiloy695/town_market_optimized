from django.template.defaultfilters import default
from locale import currency
from django.db import models
from order.models import Order
from django.db.models import Q
# Create your models here.
class Invoice(models.Model):
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)

    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateTimeField(auto_now_add=True)

    transaction_id = models.CharField(max_length=500, unique=True)
    val_id = models.CharField(max_length=255, blank=True, null=True)

    amount = models.DecimalField(decimal_places=2, max_digits=10)
    store_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    currency = models.CharField(max_length=100)

    status = models.CharField(max_length=100,default="pending")
    gateway_status = models.CharField(max_length=50, blank=True, null=True)

    card_type = models.CharField(max_length=100)
    card_brand = models.CharField(max_length=100, blank=True, null=True)
    card_issuer = models.CharField(max_length=255, blank=True, null=True)
    card_issuer_country = models.CharField(max_length=100, blank=True, null=True)

    payment_method = models.CharField(max_length=100,default="sslcommerz")

    risk_level = models.CharField(max_length=50, blank=True, null=True)
    risk_title = models.CharField(max_length=255, blank=True, null=True)

    is_ipn_verified = models.BooleanField(default=False)

    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)

    payment_date = models.DateTimeField(blank=True, null=True)
    is_paid=models.BooleanField(default=False)
    bank_tran_id=models.CharField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} -> {self.invoice_number}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=Q(status='VALID'),
                name='unique_valid_invoice_per_order'
            )
        ]