from django.contrib import admin
from .models import (
    Product, ProductCategory, ProductImage, ParentProductCategory,
    ProductCategoryOption, ProductCategoryOptionValue, ProductVariant,
    ProductVariantOptionValue
)

# Register your models here.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'shop', 'sub_category', 'is_active', 'created_at')
    list_filter = ('is_active', 'shop', 'sub_category')
    list_editable = ('is_active',)
    search_fields = ('name', 'shop__name')

admin.site.register(ProductCategory)
admin.site.register(ProductImage)
admin.site.register(ParentProductCategory)
admin.site.register(ProductCategoryOption)
admin.site.register(ProductCategoryOptionValue)
admin.site.register(ProductVariant)
admin.site.register(ProductVariantOptionValue)
