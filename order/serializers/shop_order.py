from rest_framework import serializers
from order.models import ShopOrder
from .order_item import OrderItemSerializer
from .timeline import OrderTimelineSerializer


class ShopOrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    customer_name = serializers.CharField(source='order.user.name', read_only=True)
    customer_phone = serializers.CharField(source='order.user.phone', read_only=True)
    order_number = serializers.SerializerMethodField()

    class Meta:
        model = ShopOrder
        fields = [
            'id', 'order_number', 'shop', 'shop_name', 'customer_name',
            'customer_phone', 'subtotal', 'tax', 'shipping_fee', 'discount',
            'total', 'status', 'tracking_number', 'notes', 'items', 'timeline',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]
        read_only_fields = ['id', 'subtotal', 'tax', 'shipping_fee', 'discount', 'total', 'commission_given', 'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at']

    def get_order_number(self, obj):
        return obj.get_order_number()


class ShopOrderListSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='order.user.name', read_only=True)
    customer_phone = serializers.CharField(source='order.user.phone', read_only=True)
    customer_email = serializers.CharField(source='order.user.email', read_only=True)
    shipping_address = serializers.CharField(source='order.shipping_address', read_only=True)
    city = serializers.CharField(source='order.shipping_city', read_only=True)
    area = serializers.CharField(source='order.shipping_upazilla', read_only=True)
    delivery_charge = serializers.CharField(source='shipping_fee', read_only=True)
    can_be_cancelled = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShopOrder
        fields = [
            'id', 'order_number', 'shop_name', 'total', 'status', 'commission_given',
            'item_count', 'created_at', 'customer_name', 'customer_phone', 'customer_email',
            'shipping_address', 'city', 'area', 'delivery_charge', 'can_be_cancelled', 'items',
            'subtotal', 'tax', 'discount'
        ]
        read_only_fields = fields

    def get_item_count(self, obj):
        return obj.items.count()

    def get_order_number(self, obj):
        return obj.get_order_number()

    def get_can_be_cancelled(self, obj):
        can_cancel, _ = obj.order.can_be_cancelled()
        return can_cancel
