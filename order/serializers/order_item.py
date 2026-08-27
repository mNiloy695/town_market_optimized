from rest_framework import serializers
from order.models import OrderItem
from product.serializers import ProductVariantSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product_variant.product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source='product_variant.product.shop.name', read_only=True)
    product_variant_data = ProductVariantSerializer(source='product_variant', read_only=True)
    product = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_variant', 'product_name', 'product_image',
            'shop_name', 'price_at_purchase', 'quantity', 'line_total', 'status',
            'product_variant_data', 'product'
        ]
        read_only_fields = ['id', 'price_at_purchase', 'line_total']

    def get_product_image(self, obj):
        images = obj.product_variant.product.images.first()
        if images:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(images.image.url)
            return f"/media/{images.image}"
        return None

    def get_product(self, obj):
        from product.serializers.product import ProductSerializer
        request = self.context.get('request')
        return ProductSerializer(obj.product_variant.product, context={'request': request}).data
