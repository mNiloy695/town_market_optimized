"""
Production-Ready Implementation Examples & Helpers

This file contains examples, utilities, and best practices for the order system.
"""

from decimal import Decimal
from django.db.models import Sum, Q
from . models import Order, ShopOrder, OrderItem


# ============================================================================
# BUSINESS LOGIC HELPERS
# ============================================================================

class OrderCalculations:
    """Helper class for order calculations"""
    
    @staticmethod
    def calculate_order_totals(shop_order):
        """
        Calculate and update all totals for a ShopOrder.
        Called after OrderItems are created or modified.
        """
        items_total = shop_order.items.aggregate(
            total=Sum('line_total')
        )['total'] or Decimal('0.00')
        
        tax = OrderCalculations.calculate_tax(items_total)
        shipping = OrderCalculations.calculate_shipping(shop_order.shop, items_total)
        discount = OrderCalculations.calculate_discount(items_total)
        
        shop_order.subtotal = items_total
        shop_order.tax = tax
        shop_order.shipping_fee = shipping
        shop_order.discount = discount
        shop_order.total = items_total + tax + shipping - discount
        shop_order.save()
        
        return shop_order
    
    @staticmethod
    def calculate_tax(subtotal):
        """
        Calculate tax (GST example: 17%)
        Customize based on your requirements
        """
        TAX_RATE = Decimal('0.17')  # 17% GST
        return (subtotal * TAX_RATE).quantize(Decimal('0.01'))
    
    @staticmethod
    def calculate_shipping(shop, subtotal):
        """
        Calculate shipping fee based on shop location and order value.
        Examples:
        - Free shipping over 5000
        - Weight-based pricing
        - Location-based pricing
        """
        FREE_SHIPPING_THRESHOLD = Decimal('5000.00')
        BASE_SHIPPING = Decimal('200.00')
        
        if subtotal >= FREE_SHIPPING_THRESHOLD:
            return Decimal('0.00')
        
        # You can also query shop's shipping settings
        # return shop.shipping_fee or BASE_SHIPPING
        return BASE_SHIPPING
    
    @staticmethod
    def calculate_discount(subtotal, coupon_code=None):
        """
        Calculate discount based on coupon code or automatic rules.
        """
        if coupon_code:
            # Query Coupon model here
            # coupon = Coupon.objects.get(code=coupon_code)
            # if coupon.is_valid():
            #     return coupon.calculate_discount(subtotal)
            pass
        
        # Volume-based discounts
        if subtotal >= Decimal('10000.00'):
            return (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))  # 5%
        elif subtotal >= Decimal('5000.00'):
            return (subtotal * Decimal('0.03')).quantize(Decimal('0.01'))  # 3%
        
        return Decimal('0.00')


# ============================================================================
# ANALYTICS & REPORTING
# ============================================================================

class OrderAnalytics:
    """Helper class for order analytics and reporting"""
    
    @staticmethod
    def vendor_revenue(shop, start_date=None, end_date=None):
        """Get total revenue for a vendor"""
        query = ShopOrder.objects.filter(shop=shop, status='delivered')
        
        if start_date:
            query = query.filter(created_at__gte=start_date)
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        return query.aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    
    @staticmethod
    def vendor_order_summary(shop):
        """Get order status breakdown for vendor"""
        statuses = ShopOrder.objects.filter(shop=shop).values('status').annotate(count=Count('id'))
        return {item['status']: item['count'] for item in statuses}
    
    @staticmethod
    def average_order_value(shop):
        """Calculate average order value"""
        from django.db.models import Avg
        avg = ShopOrder.objects.filter(shop=shop).aggregate(avg=Avg('total'))['avg']
        return avg or Decimal('0.00')
    
    @staticmethod
    def top_products(shop, limit=10):
        """Get top selling products for a vendor"""
        from django.db.models import Count
        return OrderItem.objects.filter(
            shop_order__shop=shop
        ).values('product_variant__product__name').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('line_total')
        ).order_by('-total_revenue')[:limit]
    
    @staticmethod
    def pending_orders_count(shop):
        """Count pending orders (actionable items)"""
        return ShopOrder.objects.filter(
            shop=shop,
            status__in=['pending', 'confirmed']
        ).count()


# ============================================================================
# PAYMENT INTEGRATION EXAMPLE
# ============================================================================

class PaymentGateway:
    """
    Example payment gateway integration (Stripe/PayPal)
    Customize based on your chosen payment provider
    """
    
    @staticmethod
    def initiate_payment(order, payment_method='card'):
        """
        Initiate payment processing
        Returns: {'success': bool, 'transaction_id': str, 'message': str}
        """
        
        if payment_method == 'cash_on_delivery':
            return {
                'success': True,
                'transaction_id': None,
                'message': 'Cash on delivery confirmed'
            }
        
        elif payment_method == 'card':
            # Example: Stripe integration
            # import stripe
            # try:
            #     intent = stripe.PaymentIntent.create(
            #         amount=int(order.total_amount * 100),
            #         currency='pkr',
            #         metadata={'order_id': order.id}
            #     )
            #     return {
            #         'success': True,
            #         'transaction_id': intent.id,
            #         'message': 'Payment initiated'
            #     }
            # except stripe.error.CardError as e:
            #     return {
            #         'success': False,
            #         'transaction_id': None,
            #         'message': f'Card declined: {e.user_message}'
            #     }
            pass
        
        elif payment_method == 'wallet':
            # Deduct from user's wallet
            # user.wallet_balance -= order.total_amount
            # user.save()
            return {
                'success': True,
                'transaction_id': f'WALLET-{order.id}',
                'message': 'Deducted from wallet'
            }
    
    @staticmethod
    def verify_payment(transaction_id):
        """Verify payment status with gateway"""
        # Call your payment gateway's API
        pass
    
    @staticmethod
    def process_refund(order, amount=None):
        """Process refund for cancelled/returned order"""
        refund_amount = amount or order.total_amount
        # Call payment gateway refund API
        pass


# ============================================================================
# ORDER WORKFLOW EXAMPLE
# ============================================================================

class OrderWorkflow:
    """
    Example of complete order workflow implementation.
    Useful for understanding the full lifecycle.
    """
    
    @staticmethod
    def auto_confirm_orders_after_timeout():
        """
        Auto-confirm orders if vendor doesn't respond within time limit.
        Should be scheduled as Celery task.
        """
        from datetime import timedelta
        from django.utils import timezone
        from . models import OrderTimeline
        
        time_limit = timezone.now() - timedelta(hours=24)  # 24 hour limit
        
        pending_orders = ShopOrder.objects.filter(
            status='pending',
            created_at__lt=time_limit
        )
        
        count = 0
        for order in pending_orders:
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Add timeline entry
            OrderTimeline.objects.create(
                shop_order=order,
                action='confirmed',
                description='Auto-confirmed after 24 hours (vendor did not respond)'
            )
            
            count += 1
        
        return count
    
    @staticmethod
    def process_return_request(shop_order, reason):
        """
        Process a return request initiated by customer.
        """
        from . models import OrderTimeline
        
        if shop_order.status != 'delivered':
            raise ValueError('Only delivered orders can be returned')
        
        shop_order.status = 'return_requested'
        shop_order.save()
        
        OrderTimeline.objects.create(
            shop_order=shop_order,
            action='return_requested',
            description=f'Return requested by customer. Reason: {reason}',
            created_by=shop_order.order.user
        )
    
    @staticmethod
    def complete_return(shop_order):
        """
        Mark return as completed and process refund.
        Should be called after vendor confirms receipt of returned items.
        """
        from . models import OrderTimeline
        
        if shop_order.status != 'return_requested':
            raise ValueError('Order must be in return_requested status')
        
        # Restore stock
        for item in shop_order.items.all():
            item.product_variant.stock += item.quantity
            item.product_variant.save()
        
        # Process refund
        # PaymentGateway.process_refund(shop_order.order)
        
        shop_order.status = 'returned'
        shop_order.save()
        
        OrderTimeline.objects.create(
            shop_order=shop_order,
            action='returned',
            description='Return completed. Refund processed.'
        )


# ============================================================================
# DATA VALIDATION HELPERS
# ============================================================================

class OrderValidation:
    """Validation helpers for order operations"""
    
    @staticmethod
    def validate_checkout_data(cart, shipping_data):
        """Validate all data required for checkout"""
        errors = []
        
        # Validate cart
        if not cart.items.exists():
            errors.append('Cart is empty')
        
        # Validate stock
        for cart_item in cart.items.all():
            if cart_item.product_variant.stock < cart_item.quantity:
                errors.append(
                    f'Insufficient stock for {cart_item.product_variant.product.name}'
                )
        
        # Validate shipping data
        required_fields = ['shipping_address', 'shipping_city', 'phone_number']
        for field in required_fields:
            if not shipping_data.get(field, '').strip():
                errors.append(f'{field} is required')
        
        return errors
    
    @staticmethod
    def validate_status_transition(current_status, new_status):
        """Validate if status transition is allowed"""
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
        
        return new_status in valid_transitions.get(current_status, [])


# ============================================================================
# TESTING HELPERS
# ============================================================================

class OrderTestFactory:
    """
    Helper class to create test data for order system.
    Usage: factory = OrderTestFactory()
           order = factory.create_complete_order()
    """
    
    @staticmethod
    def create_test_order(user, num_shops=2, items_per_shop=2):
        """Create a complete test order with all relationships"""
        from django.utils import timezone
        from cart.models import Cart, CartItem
        from product.models import Product, ProductVariant
        from shop.models import Shop
        
        # Create master order
        order = Order.objects.create(
            user=user,
            total_amount=Decimal('5000.00'),
            status='confirmed',
            shipping_address='123 Test Street',
            shipping_city='Test City',
            phone_number='+92 300 1234567',
            payment_method='cash_on_delivery'
        )
        
        # This is a simplified example
        # In reality, you'd create actual products and variants
        
        return order


# ============================================================================
# PERFORMANCE OPTIMIZATION
# ============================================================================

def get_user_orders_optimized(user):
    """
    Optimized query for getting user's orders.
    Uses select_related and prefetch_related to avoid N+1 queries.
    """
    return Order.objects.filter(user=user).prefetch_related(
        'shop_orders__items__product_variant__product__shop',
        'shop_orders__timeline'
    ).select_related('user')


def get_vendor_orders_optimized(shop):
    """
    Optimized query for getting vendor's orders.
    """
    return ShopOrder.objects.filter(shop=shop).prefetch_related(
        'items__product_variant__product',
        'timeline'
    ).select_related('order__user')


# ============================================================================
# MIGRATION HELPERS (For Upgrading Existing Systems)
# ============================================================================

def migrate_old_orders_to_new_system():
    """
    Example function to migrate legacy orders to new multi-vendor system.
    This would be used if you had a simple order system before.
    """
    # This is a placeholder showing how you might migrate
    # Actual implementation depends on your old schema
    
    # 1. Fetch all old orders
    # 2. For each old order:
    #    a. Create a new Order
    #    b. Group items by shop (if you have shop info in old system)
    #    c. Create ShopOrders
    #    d. Create OrderItems
    #    e. Create OrderTimeline entries
    # 3. Verify migration
    # 4. Archive old orders
    pass
