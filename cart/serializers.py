from rest_framework import serializers
from .models import Cart, CartItem
from product.models import ProductVariant

class CartItemSerializer(serializers.ModelSerializer):
    product_variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    product_variant_data = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product_variant', 'product_variant_data', 'quantity', 'added_at', 'updated_at']
        read_only_fields = ['cart', 'added_at', 'updated_at']

    def get_product_variant_data(self, obj):
        image_url = None
        if obj.product_variant.product.images.exists():
            image_url = obj.product_variant.product.images.first().image.url
        return {
            'id': obj.product_variant.id,
            'price': obj.product_variant.price,
            'stock': obj.product_variant.stock,
            'description': obj.product_variant.description,
            'image': image_url,
        }

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'created_at', 'updated_at', 'items', 'total']
        read_only_fields = ['user', 'created_at', 'updated_at', 'items', 'total']

    def get_total(self, obj):
        return sum(item.product_variant.price * item.quantity for item in obj.items.all())


class AddToCartSerializer(serializers.Serializer):
    variant_id = serializers.CharField(required=False)
    quantity = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        variant_id = attrs.get('variant_id')
        quantity = attrs.get('quantity')
        if not variant_id:
            raise serializers.ValidationError({"error": "Product variant ID is required."})
        if quantity is None:
            raise serializers.ValidationError({"error": "Quantity is required."})
        try:
            self.variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError({"error": "Product variant does not exist."})
        return attrs