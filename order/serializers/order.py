from rest_framework import serializers
from order.models import Order
from .shop_order import ShopOrderDetailSerializer


class OrderDetailSerializer(serializers.ModelSerializer):
    shop_orders = ShopOrderDetailSerializer(many=True, read_only=True)
    can_be_cancelled = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'total_amount', 'status', 'is_paid',
            'shipping_address', 'shipping_city', 'shipping_postal_code',
            'shipping_country', 'phone_number', 'payment_method',
            'shop_orders', 'created_at', 'updated_at', 'confirmed_at',
            'can_be_cancelled', 'cancellation_reason'
        ]
        read_only_fields = ['id', 'order_number', 'total_amount', 'status', 'created_at', 'updated_at', 'confirmed_at']

    def get_can_be_cancelled(self, obj):
        can_cancel, _ = obj.can_be_cancelled()
        return can_cancel

    def get_cancellation_reason(self, obj):
        can_cancel, reason = obj.can_be_cancelled()
        return reason if not can_cancel else None


class OrderListSerializer(serializers.ModelSerializer):
    shop_count = serializers.SerializerMethodField()
    can_be_cancelled = serializers.SerializerMethodField()
    cancellation_reason = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'total_amount', 'status', 'shop_count', 'created_at',
            'can_be_cancelled', 'cancellation_reason', 'confirmed_at'
        ]
        read_only_fields = fields

    def get_shop_count(self, obj):
        return obj.shop_orders.count()

    def get_can_be_cancelled(self, obj):
        can_cancel, _ = obj.can_be_cancelled()
        return can_cancel

    def get_cancellation_reason(self, obj):
        can_cancel, reason = obj.can_be_cancelled()
        return reason if not can_cancel else None
