from django.db import models
from .product import Product
from .category import ProductCategoryOptionValue


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    stock = models.IntegerField()
    reserved_quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - Variant {self.id}"

    @property
    def available_stock(self):
        return self.stock - self.reserved_quantity

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock__gte=0),
                name='stock_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name='reserved_quantity_non_negative',
            ),
        ]


class ProductVariantOptionValue(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='option_values')
    option_value = models.ForeignKey(ProductCategoryOptionValue, on_delete=models.CASCADE, related_name='variant_links')

    class Meta:
        unique_together = ('variant', 'option_value')

    def __str__(self):
        return f"{self.variant} - {self.option_value.value}"
