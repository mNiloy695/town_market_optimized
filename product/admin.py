from django.contrib import admin
from .models import Product,ProductCategory,ProductImage,ParentProductCategory,ProductCategoryOption,ProductCategoryOptionValue,ProductVariant,ProductVariantOptionValue
# Register your models here.

admin.site.register(Product)
admin.site.register(ProductCategory)
admin.site.register(ProductImage)
admin.site.register(ParentProductCategory)
admin.site.register(ProductCategoryOption)
admin.site.register(ProductCategoryOptionValue)
admin.site.register(ProductVariant)
admin.site.register(ProductVariantOptionValue)

