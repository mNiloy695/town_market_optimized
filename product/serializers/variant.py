from rest_framework import serializers
from product.models import ProductVariant, ProductVariantOptionValue


class ProductVariantOptionValueSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    option_value_data = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariantOptionValue
        fields = ['id', 'variant', 'option_value', 'option_value_data']
        read_only_fields = ['variant']

    def get_option_value_data(self, obj):
        return {
            "option_name": obj.option_value.product_category_option.name,
            "option_id": obj.option_value.product_category_option.id,
            "value_id": obj.option_value.id,
            "value_name": obj.option_value.value,
        }


class ProductVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    option_values = ProductVariantOptionValueSerializer(many=True)
    available_stock = serializers.SerializerMethodField(read_only=True)
    is_stock = serializers.SerializerMethodField(read_only=True)

    def get_available_stock(self, obj):
        return max(obj.stock - obj.reserved_quantity, 0)

    def get_is_stock(self, obj):
        return self.get_available_stock(obj) > 0

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'price', 'description', 'stock',
            'reserved_quantity', 'available_stock', 'is_stock', 'option_values'
        ]
        read_only_fields = ['product', 'reserved_quantity']


class RestockSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=10000)
