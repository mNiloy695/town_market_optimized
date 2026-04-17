import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from product.models import Product, ProductVariant

p = Product.objects.get(id=1)
print(f"Product: {p.name}")
for v in p.variants.all():
    opts = list(v.option_values.values_list('option_value_id', flat=True))
    print(f"Variant {v.id}: {opts} (Stock: {v.stock})")
