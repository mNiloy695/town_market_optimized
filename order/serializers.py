from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from django.db import transaction
from .models import Order, ShopOrder, OrderItem, OrderTimeline
from cart.models import Cart, CartItem
from product.models import ProductVariant
from product.serializers import ProductVariantSerializer
from shop.models import Shop
from accounts.models import CustomUser


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for individual order items"""
    product_name = serializers.CharField(source='product_variant.product.name', read_only=True)

    product_image = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source='product_variant.product.shop.name', read_only=True)
    product_variant_data = ProductVariantSerializer(source='product_variant', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_variant', 'product_name', 'product_image',
            'shop_name', 'price_at_purchase', 'quantity', 'line_total', 'status','product_variant_data'
        ]
        read_only_fields = ['id', 'price_at_purchase', 'line_total']
    
    def get_product_image(self, obj):
        """Get the first image of the product"""
        images = obj.product_variant.product.images.first()
        if images:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(images.image.url)
            return f"/media/{images.image}"
        return None


class OrderTimelineSerializer(serializers.ModelSerializer):
    """Timeline events for an order"""
    user_name = serializers.CharField(source='created_by.name', read_only=True)
    
    class Meta:
        model = OrderTimeline
        fields = ['id', 'action', 'description', 'created_at', 'user_name']
        read_only_fields = ['id', 'created_at']


class ShopOrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for shop orders (for vendors and customers)"""
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
        read_only_fields = ['id', 'subtotal', 'tax', 'shipping_fee', 'discount', 'total']
    
    def get_order_number(self, obj):
        return obj.get_order_number()


class ShopOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order lists"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    
    class Meta:
        model = ShopOrder
        fields = [
            'id', 'order_number', 'shop_name', 'total', 'status',
            'item_count', 'created_at'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def get_order_number(self, obj):
        return obj.get_order_number()



class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed order serializer for customers"""
    shop_orders = ShopOrderDetailSerializer(many=True, read_only=True)
    
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'total_amount', 'status', 'is_paid',
            'shipping_address', 'shipping_city', 'shipping_postal_code',
            'shipping_country', 'phone_number', 'payment_method',
            'shop_orders', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'total_amount', 'status', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order lists"""
    shop_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'total_amount', 'status', 'shop_count', 'created_at'
        ]
        read_only_fields = fields
    
    def get_shop_count(self, obj):
        return obj.shop_orders.count()


class CheckoutSerializer(serializers.Serializer):
    """
    Serializer for checkout process.
    Validates cart and creates orders.
    """
    # Shipping information
    shipping_address = serializers.CharField(max_length=2500)
    shipping_city = serializers.CharField(max_length=1000)
    shipping_postal_code = serializers.CharField(max_length=200)
    shipping_country = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20)
    
    # Payment information
    payment_method = serializers.ChoiceField(
        choices=['sslcommerz'],
        default='sslcommerz'
    )
    
    def validate(self, data):
        """Validate that cart has items"""
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required")

        shipping_address = data.get('shipping_address',None)
        shipping_city = data.get('shipping_city',None)
        shipping_postal_code = data.get('shipping_postal_code',None)
        shipping_country = data.get('shipping_country',None)
        phone_number = data.get('phone_number',None)
        if not (shipping_address and shipping_city and shipping_country and shipping_postal_code and phone_number):
            raise serializers.ValidationError({"error":"shipping address, city, postal code, country and phone number are required"})        
        
        try:
            cart = Cart.objects.get(user=request.user)
            if not cart.items.exists():
                raise serializers.ValidationError("Cart is empty")
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found")
        
        return data
    
    def create(self, validated_data):
        """
        Create order and shop_orders from cart.
        This is handled by the view, not by the serializer.
        """
        raise NotImplementedError(
            "Use CheckoutView.perform_checkout() instead of serializer.save()"
        )


class VendorOrderStatsSerializer(serializers.Serializer):
    """Statistics for vendor dashboard"""
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class ShopOrderStatusUpdateSerializer(serializers.ModelSerializer):
    """For vendor to update order status"""
    class Meta:
        model = ShopOrder
        fields = ['status', 'tracking_number', 'notes']
    
    def validate(self, data):
        """Validate status transitions"""
        instance = self.instance
        value = data.get('status')
        
        if not value:
            return data

        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['processing', 'cancelled'],
            'processing': ['shipped', 'cancelled'],
            'shipped': ['delivered'],
            'delivered': [],
            'cancelled': [],
            'return_requested': ['returned', 'cancelled'],
            'returned': [],
        }
        
        if instance and instance.status in valid_transitions:
            if value not in valid_transitions[instance.status]:
                raise BadRequest(
                   {"error": f"Invalid status transition from {instance.status} to {value}"}
                )
        
        return data
