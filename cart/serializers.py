from rest_framework import serializers
from .models import Cart, CartItem
from product.models import ProductVariant
from product.serializers import ProductVariantSerializer

class CartItemSerializer(serializers.ModelSerializer):
    product_variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    product_variant_data = ProductVariantSerializer(source="product_variant", read_only=True)
    product_data = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'product_variant', 'product_variant_data', 'product_data', 'quantity', 'added_at', 'updated_at']
        read_only_fields = ['cart', 'added_at', 'updated_at']

    def get_product_data(self, obj):
        product = obj.product_variant.product
        from product.serializers import ProductImageSerializer
        return {
            'id': product.id,
            'name': product.name,
            'images': ProductImageSerializer(product.images.all(), many=True, context=self.context).data,
            'shop_data': {
                'shop_name': product.shop.name,
                'shop_id': product.shop.id
            }
        }


    # def get_product_variant_data(self, obj):
    #     image_url = None
    #     if obj.product_variant.product.images.exists():
    #         image_url = obj.product_variant.product.images.first().image.url
    #     is_available = obj.product_variant.stock >= obj.quantity
    #     return {
    #         'id': obj.product_variant.id,
    #         'price': obj.product_variant.price,
    #         'stock': obj.product_variant.stock,
    #         'description': obj.product_variant.description,
    #         'image': image_url,
    #         'is_available': is_available,
    #     }

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    shipping_total = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    booking_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'created_at', 'updated_at', 'items', 'subtotal', 'shipping_total', 'grand_total', 'booking_amount']
        read_only_fields = ['user', 'created_at', 'updated_at', 'items']

    def get_subtotal(self, obj):
        return sum(item.product_variant.price * item.quantity for item in obj.items.all())

    def get_shipping_total(self, obj):
        from django.conf import settings
        shipping_fee_per_shop = getattr(settings, 'SHIPPING_FEE', 50)
        
        # Get unique shops in the cart
        shops = set(item.product_variant.product.shop_id for item in obj.items.all())
        return len(shops) * shipping_fee_per_shop

    def get_grand_total(self, obj):
        return self.get_subtotal(obj) + self.get_shipping_total(obj)

    def get_booking_amount(self, obj):
        # Booking amount is the shipping total as per the new business logic
        return self.get_shipping_total(obj)


class AddToCartSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_variant_id(self, value):
        try:
            self.variant = ProductVariant.objects.get(id=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Product variant does not exist.")
        return value