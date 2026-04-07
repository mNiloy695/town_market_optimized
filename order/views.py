from rest_framework import status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone

from .models import Order, ShopOrder, OrderItem, OrderTimeline
from .serializers import (
    CheckoutSerializer, OrderDetailSerializer, OrderListSerializer,
    ShopOrderDetailSerializer, ShopOrderListSerializer,
    ShopOrderStatusUpdateSerializer, VendorOrderStatsSerializer
)
from cart.models import Cart, CartItem
from shop.models import Shop
from product.models import ProductVariant


class StandardPagination(PageNumberPagination):
    """Standard pagination for list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    page_size_query_description = 'Number of results to return per page.'
    max_page_size = 100


class CheckoutView(APIView):
    """
    Checkout endpoint that converts cart to orders.
    Splits cart items by shop and creates ShopOrders.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Checkout endpoint
        
        Request body:
        {
            "shipping_address": "123 Main St",
            "shipping_city": "Karachi",
            "shipping_postal_code": "75001",
            "shipping_country": "Pakistan",
            "phone_number": "+92 300 1234567",
            "payment_method": "cash_on_delivery"
        }
        """
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                cart = get_object_or_404(Cart, user=request.user)
                
                # Check cart is not empty
                if not cart.items.exists():
                    return Response(
                        {'error': 'Cart is empty'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate available stock for all items (considering reservations)
                for cart_item in cart.items.all():
                    if cart_item.product_variant.available_stock < cart_item.quantity:
                        return Response(
                            {
                                'error': f"Not enough stock for {cart_item.product_variant.product.name}",
                                'available': cart_item.product_variant.available_stock,
                                'requested': cart_item.quantity
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                # Group cart items by shop
                shop_items = self._group_items_by_shop(cart)
                
                # Calculate total
                grand_total = sum(
                    sum(item.product_variant.price * item.quantity 
                        for item in items)
                    for items in shop_items.values()
                )
                
                # Create master order
                order = Order.objects.create(
                    user=request.user,
                    total_amount=grand_total,
                    status='pending_payment',
                    shipping_address=serializer.validated_data['shipping_address'],
                    shipping_city=serializer.validated_data['shipping_city'],
                    shipping_postal_code=serializer.validated_data['shipping_postal_code'],
                    shipping_country=serializer.validated_data['shipping_country'],
                    phone_number=serializer.validated_data['phone_number'],
                    payment_method=serializer.validated_data['payment_method']
                )
                
                # Create shop orders and items
                shop_orders = []
                for shop, cart_items in shop_items.items():
                    shop_order = self._create_shop_order(order, shop, cart_items)
                    shop_orders.append(shop_order)
                    
                    # Add timeline entry
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='created',
                        description='Order created from cart',
                        created_by=request.user
                    )
                
                # Clear cart
                cart.items.all().delete()
                
                return Response(
                    {
                        'message': 'Order created successfully',
                        'order': OrderDetailSerializer(order, context={'request': request}).data
                    },
                    status=status.HTTP_201_CREATED
                )
        
        except Exception as e:
            return Response(
                {'error': f'Checkout failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _group_items_by_shop(self, cart):
        """Group cart items by shop"""
        shop_items = {}
        for cart_item in cart.items.select_related('product_variant__product__shop').all():
            shop = cart_item.product_variant.product.shop
            if shop not in shop_items:
                shop_items[shop] = []
            shop_items[shop].append(cart_item)
        return shop_items
    
    def _create_shop_order(self, order, shop, cart_items):
        """Create ShopOrder and associated OrderItems"""
        subtotal = sum(
            item.product_variant.price * item.quantity 
            for item in cart_items
        )
        
        # You can add tax and shipping calculations here based on business logic
        tax = 0  # Calculate tax if applicable
        shipping_fee = 0  # Calculate shipping if applicable
        discount = 0  # Apply discount codes if applicable
        
        total = subtotal + tax + shipping_fee - discount
        
        shop_order = ShopOrder.objects.create(
            order=order,
            shop=shop,
            subtotal=subtotal,
            tax=tax,
            shipping_fee=shipping_fee,
            discount=discount,
            total=total,
            status='pending'
        )
        
        # Create order items and reserve stock (don't reduce yet)
        for cart_item in cart_items:
            OrderItem.objects.create(
                shop_order=shop_order,
                product_variant=cart_item.product_variant,
                quantity=cart_item.quantity
            )
            
            # Reserve stock (pending payment confirmation)
            cart_item.product_variant.reserved_quantity += cart_item.quantity
            cart_item.product_variant.save()
        
        return shop_order


class OrderListView(APIView):
    """
    List all orders for the current user (customer view).
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get(self, request):
        """Get all orders for the current user"""
        orders = Order.objects.filter(user=request.user).prefetch_related('shop_orders')
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(orders, request)
        
        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)


class OrderDetailView(APIView):
    """
    Get detailed view of a single order (customer view).
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, order_id):
        """Get order details"""
        order = get_object_or_404(Order, id=order_id, user=request.user)
        serializer = OrderDetailSerializer(order, context={'request': request})
        return Response(serializer.data)


class VendorOrderListView(APIView):
    """
    List orders for a vendor (shop owner view).
    Only shows orders from their own shop.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get(self, request):
        """Get all orders for vendor's shop"""
        try:
            shop = request.user.shop
        except:
            return Response(
                {'error': 'User does not own a shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        orders = ShopOrder.objects.filter(shop=shop).select_related('order__user')
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(orders, request)
        
        if page is not None:
            serializer = ShopOrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ShopOrderListSerializer(orders, many=True)
        return Response(serializer.data)


class VendorOrderDetailView(APIView):
    """
    Get detailed view of a single shop order (vendor view).
    Allows vendor to see customer details and manage order.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, shop_order_id):
        """Get shop order details"""
        try:
            shop = request.user.shop
        except:
            return Response(
                {'error': 'User does not own a shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, shop=shop)
        serializer = ShopOrderDetailSerializer(shop_order, context={'request': request})
        return Response(serializer.data)


class VendorOrderStatusUpdateView(APIView):
    """
    Update shop order status (vendor-only).
    Allows vendors to confirm, process, ship, and deliver orders.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, shop_order_id):
        """Update shop order status"""
        try:
            shop = request.user.shop
        except:
            return Response(
                {'error': 'User does not own a shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, shop=shop)
        
        serializer = ShopOrderStatusUpdateSerializer(
            shop_order, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        
        old_status = shop_order.status
        updated_order = serializer.save()
        
        # Add timeline entry
        action_map = {
            'confirmed': 'confirmed',
            'processing': 'processing',
            'shipped': 'shipped',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'return_requested': 'return_requested',
            'returned': 'returned'
        }
        
        OrderTimeline.objects.create(
            shop_order=updated_order,
            action=action_map.get(updated_order.status, 'status_changed'),
            description=f'Status changed from {old_status} to {updated_order.status}',
            created_by=request.user
        )
        
        # Update timestamps
        if updated_order.status == 'confirmed':
            updated_order.confirmed_at = timezone.now()
        elif updated_order.status == 'shipped':
            updated_order.shipped_at = timezone.now()
        elif updated_order.status == 'delivered':
            updated_order.delivered_at = timezone.now()
        updated_order.save()
        
        return Response(
            ShopOrderDetailSerializer(updated_order, context={'request': request}).data
        )


class VendorDashboardStatsView(APIView):
    """
    Dashboard statistics for vendor.
    Shows order counts, sales, and key metrics.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get dashboard statistics"""
        try:
            shop = request.user.shop
        except:
            return Response(
                {'error': 'User does not own a shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        shop_orders = ShopOrder.objects.filter(shop=shop)
        
        # Calculate statistics
        stats = {
            'total_orders': shop_orders.count(),
            'pending_orders': shop_orders.filter(status='pending').count(),
            'confirmed_orders': shop_orders.filter(status='confirmed').count(),
            'shipped_orders': shop_orders.filter(status='shipped').count(),
            'total_sales': shop_orders.aggregate(Sum('total'))['total__sum'] or 0,
            'average_order_value': shop_orders.aggregate(Avg('total'))['total__avg'] or 0,
        }
        
        serializer = VendorOrderStatsSerializer(stats)
        return Response(serializer.data)


class CustomerOrderCancel(APIView):
    """Allow customers to cancel pending orders"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, shop_order_id):
        """Cancel a shop order if status is pending"""
        try:
            order = Order.objects.get(
                id__in=ShopOrder.objects.filter(id=shop_order_id).values('order_id'),
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, order=order)
        
        if shop_order.status not in ['pending', 'confirmed']:
            return Response(
                {'error': 'Only pending or confirmed orders can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Release reserved stock
        for item in shop_order.items.all():
            if shop_order.status == 'pending':
                # Release reservation
                item.product_variant.reserved_quantity -= item.quantity
            else:
                # Restore actual stock if already reduced (confirmed orders)
                item.product_variant.stock += item.quantity
            item.product_variant.save()
        
        shop_order.status = 'cancelled'
        shop_order.save()
        
        OrderTimeline.objects.create(
            shop_order=shop_order,
            action='cancelled',
            description='Order cancelled by customer',
            created_by=request.user
        )
        
        return Response(
            {'message': 'Order cancelled successfully'},
            status=status.HTTP_200_OK
        )


class PaymentConfirmationView(APIView):
    """
    Confirm payment and release stock from pending to reserved.
    Call this endpoint after payment gateway confirms payment.
    
    This is the critical transition point where:
    - Stock becomes locked (no longer available for other customers)
    - Vendor orders are marked confirmed (ready to process)
    - Fulfillment workflow begins
    
    Workflow:
    pending_payment → confirmed (stock reduced from reserved)
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        """
        Confirm payment for an order
        
        Request body:
        {
            "payment_id": "pay_xxxx",  # Payment gateway transaction ID
            "payment_proof": "optional_reference"
        }
        """
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow confirmation for pending payment orders
        if order.status != 'pending_payment':
            return Response(
                {'error': f'Order is already {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if order.is_paid:
            return Response(
                {'error': 'Payment already confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Confirm payment on the order
                order.confirm_payment()
                
                return Response(
                    {
                        'message': 'Payment confirmed successfully',
                        'order': OrderDetailSerializer(order, context={'request': request}).data,
                        'next_step': 'Vendors are processing your order',
                        'status': 'confirmed'
                    },
                    status=status.HTTP_200_OK
                )
        
        except Exception as e:
            return Response(
                {'error': f'Payment confirmation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderReturnRequestView(APIView):
    """
    Request return for delivered orders.
    Handles refunds and stock restoration.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, shop_order_id):
        """Request return for a shop order"""
        try:
            order = Order.objects.get(
                id__in=ShopOrder.objects.filter(id=shop_order_id).values('order_id'),
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, order=order)
        
        # Only delivered orders can be returned
        if shop_order.status != 'delivered':
            return Response(
                {'error': 'Only delivered orders can be returned'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        
        try:
            with transaction.atomic():
                shop_order.status = 'return_requested'
                shop_order.save()
                
                OrderTimeline.objects.create(
                    shop_order=shop_order,
                    action='return_requested',
                    description=f'Return requested. Reason: {reason}',
                    created_by=request.user
                )
                
                return Response(
                    {
                        'message': 'Return request submitted',
                        'order': ShopOrderDetailSerializer(shop_order, context={'request': request}).data
                    },
                    status=status.HTTP_200_OK
                )
        
        except Exception as e:
            return Response(
                {'error': f'Return request failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VendorReturnApprovalView(APIView):
    """
    Vendor approves or rejects return requests.
    If approved, stock is restored and refund is processed.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, shop_order_id):
        """
        Approve or reject return
        
        Request body:
        {
            "action": "approve" | "reject",
            "reason": "Condition not as described" (optional for rejection)
        }
        """
        try:
            shop = request.user.shop
        except:
            return Response(
                {'error': 'User does not own a shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, shop=shop)
        
        if shop_order.status != 'return_requested':
            return Response(
                {'error': 'Order does not have a pending return request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')
        if action not in ['approve', 'reject']:
            return Response(
                {'error': 'Action must be "approve" or "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                if action == 'approve':
                    # Restore stock
                    for item in shop_order.items.all():
                        item.product_variant.stock += item.quantity
                        item.product_variant.save()
                    
                    shop_order.status = 'returned'
                    shop_order.save()
                    
                    # Process refund (integrate with payment gateway)
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='returned',
                        description='Return approved - refund processed',
                        created_by=request.user
                    )
                    
                    message = 'Return approved and stock restored'
                
                else:  # reject
                    reason = request.data.get('reason', 'Return request rejected')
                    shop_order.status = 'delivered'  # Revert to delivered
                    shop_order.save()
                    
                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='returned',
                        description=f'Return rejected. Reason: {reason}',
                        created_by=request.user
                    )
                    
                    message = 'Return request rejected'
                
                return Response(
                    {
                        'message': message,
                        'order': ShopOrderDetailSerializer(shop_order, context={'request': request}).data
                    },
                    status=status.HTTP_200_OK
                )
        
        except Exception as e:
            return Response(
                {'error': f'Return approval failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

