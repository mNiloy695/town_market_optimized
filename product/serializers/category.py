from rest_framework import serializers
from product.models import (
    ParentProductCategory, ProductCategory,
    ProductCategoryOption, ProductCategoryOptionValue
)


class ParentProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentProductCategory
        fields = '__all__'


class ProductCategorySerializer(serializers.ModelSerializer):
    parent_data = ParentProductCategorySerializer(source='parent', read_only=True)

    class Meta:
        model = ProductCategory
        fields = '__all__'


class ProductCategoryOptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategoryOptionValue
        fields = '__all__'


class ProductCategoryOptionSerializer(serializers.ModelSerializer):
    values = ProductCategoryOptionValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductCategoryOption
        fields = '__all__'
