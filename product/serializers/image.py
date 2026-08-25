from rest_framework import serializers
from product.models import ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = ProductImage
        fields = ['id', 'image']
        read_only_fields = ['product']


class ProductImageDeleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id']
