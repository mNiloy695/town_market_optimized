from rest_framework import serializers
from .models import (
    Product, ProductCategory, ProductImage, ParentProductCategory, 
    ProductCategoryOption, ProductCategoryOptionValue, ProductVariant, 
    ProductVariantOptionValue
)

class ParentProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model=ParentProductCategory
        fields='__all__'

class ProductCategorySerializer(serializers.ModelSerializer):
    parent=ParentProductCategorySerializer(read_only=True)
    class Meta:
        model=ProductCategory
        fields='__all__'

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model=ProductImage
        fields='__all__'

class ProductCategoryOptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model=ProductCategoryOptionValue
        fields='__all__'

class ProductCategoryOptionSerializer(serializers.ModelSerializer):
    values = ProductCategoryOptionValueSerializer(many=True, read_only=True)
    class Meta:
        model=ProductCategoryOption
        fields='__all__'

class ProductVariantOptionValueSerializer(serializers.ModelSerializer):
    
    option_value_data=serializers.SerializerMethodField()
    class Meta:
        model=ProductVariantOptionValue
        fields=['id', 'variant', 'option_value','option_value_data']
        read_only_fields = ['variant']
    def get_option_value_data(self,obj):
        return {
            "option_name":obj.option_value.product_category_option.name,
            "option_id":obj.option_value.product_category_option.id,
            "value_id":obj.option_value.id,
            "value_name":obj.option_value.value,
        }

class ProductVariantSerializer(serializers.ModelSerializer):
    option_values = ProductVariantOptionValueSerializer(many=True)
    class Meta:
        model=ProductVariant
        fields=['id', 'product', 'price', 'description', 'stock', 'option_values']
        read_only_fields = ['product']

class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True)
    
    class Meta:
        model=Product
        fields=['id', 'name', 'slug', 'shop', 'sub_category', 'variants']

    def create(self, validated_data):
        variants_data = validated_data.pop('variants')
        product = Product.objects.create(**validated_data)
        
        for variant_data in variants_data:
            option_values_data = variant_data.pop('option_values')
            variant = ProductVariant.objects.create(product=product, **variant_data)
            
            for ov_data in option_values_data:
                ProductVariantOptionValue.objects.create(variant=variant, **ov_data)
        
        return product
