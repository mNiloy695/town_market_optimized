from django.db import models
from slugify import slugify
from .category import ProductCategory


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    shop = models.ForeignKey('shop.Shop', on_delete=models.CASCADE, related_name='products')
    sub_category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products')

    def __str__(self):
        return f'{self.name} - {self.id}'

    def save(self, *args, **kwargs):
        from django.db import IntegrityError, transaction
        from product.utils import set_unique_slug
        
        attempts = 5
        counter = 1
        while attempts > 0:
            set_unique_slug(self)
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                err_msg = str(e).lower()
                if 'slug' in err_msg or 'unique' in err_msg:
                    from slugify import slugify
                    base_slug = slugify(self.name)
                    self.slug = f"{base_slug}-{counter}"
                    counter += 1
                    attempts -= 1
                else:
                    raise e
        super().save(*args, **kwargs)
