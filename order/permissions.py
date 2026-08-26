"""
Custom permissions for order system.

Provides fine-grained access control for:
- Customer order access
- Vendor order access
- Admin operations
"""

from rest_framework import permissions
from .models import Order, ShopOrder


class IsCustomer(permissions.BasePermission):
    """
    Permission for customer-only endpoints.
    Allows authenticated users (buyers).
    """
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the order"""
        if isinstance(obj, Order):
            return obj.user == request.user
        return False


class IsVendor(permissions.BasePermission):
    """
    Permission for vendor-only endpoints.
    Only users who own an active shop can access.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        if not hasattr(request.user, 'shop'):
            return False
        shop = request.user.shop
        return shop.is_active and not shop.is_deactivated and shop.status == 'approved'


class IsVendorOfShop(permissions.BasePermission):
    """
    Permission to ensure vendor can only access their own shop's orders.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        if not hasattr(request.user, 'shop'):
            return False
        shop = request.user.shop
        return shop.is_active and not shop.is_deactivated and shop.status == 'approved'
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the shop in the order"""
        if isinstance(obj, ShopOrder):
            return obj.shop.owner == request.user
        return False


class IsOrderOwner(permissions.BasePermission):
    """
    Permission to check if user owns the order.
    """
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Order):
            return obj.user == request.user
        elif isinstance(obj, ShopOrder):
            return obj.order.user == request.user
        return False


class IsReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access.
    """
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class CanCancelOrder(permissions.BasePermission):
    """
    Permission to check if order can be cancelled.
    Only pending or confirmed orders can be cancelled.
    """
    
    message = "Only pending or confirmed orders can be cancelled."
    
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, ShopOrder):
            return obj.order.user == request.user and obj.status in ['pending', 'confirmed']
        return False


class CanUpdateOrderStatus(permissions.BasePermission):
    """
    Permission for vendors to update order status.
    Vendor must own an active shop and the transition must be valid.
    """
    
    message = "You cannot update this order status."
    
    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, ShopOrder):
            return False
        
        if not request.user.is_active:
            return False
        
        shop = obj.shop
        if shop.owner != request.user:
            return False
        
        if not shop.is_active or shop.is_deactivated or shop.status != 'approved':
            return False
        
        return True


# ============================================================================
# MIXINS FOR VIEWS
# ============================================================================

class CustomerOrderMixin:
    """
    Mixin to ensure customers can only access their own orders.
    """
    
    def get_queryset(self):
        """Filter orders to only those owned by the current user"""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)


class VendorOrderMixin:
    """
    Mixin to ensure vendors can only access their own shop's orders.
    """
    
    def get_queryset(self):
        """Filter orders to only those from vendor's shop"""
        queryset = super().get_queryset()
        
        # Check if user is a vendor
        if not hasattr(self.request.user, 'shop'):
            return queryset.none()
        
        return queryset.filter(shop=self.request.user.shop)


# ============================================================================
# SECURITY UTILITIES
# ============================================================================

class OrderSecurityValidator:
    """
    Validation utilities for order security.
    """
    
    @staticmethod
    def validate_checkout_access(user):
        """
        Validate if user can checkout.
        Could include checks for:
        - Account suspension
        - Payment history
        - Geographic restrictions
        """
        if not user.is_active:
            raise PermissionError("Your account is inactive")
        
        # Add more checks as needed
        return True
    
    @staticmethod
    def validate_vendor_access(user):
        """
        Validate if user is a vendor and shop is active.
        """
        if not hasattr(user, 'shop'):
            raise PermissionError("User does not own a shop")
        
        shop = user.shop
        
        if not shop.is_active:
            raise PermissionError("Your shop is inactive")
        
        if shop.is_deactivated:
            raise PermissionError("Your shop has been deactivated")
        
        return True
    
    @staticmethod
    def log_order_access(user, order_id, action):
        """
        Log order access for security audit.
        Useful for detecting suspicious activity.
        """
        # This could be logged to:
        # - Database audit table
        # - Log file
        # - Third-party logging service
        import logging
        logger = logging.getLogger('order_security')
        logger.info(f"User {user.id} {action} order {order_id}")


# ============================================================================
# FIELD-LEVEL PERMISSIONS
# ============================================================================

class BasePricePermission(permissions.BasePermission):
    """
    Custom permission that checks if the user should see prices.
    Useful if you have guest checkout or guest browsing.
    """
    
    def has_permission(self, request, view):
        # Only authenticated users can see prices in order details
        return bool(request.user and request.user.is_authenticated)


# ============================================================================
# RATE LIMITING (for production)
# ============================================================================

"""
For production, use:
1. Django-RateLimiting
2. Django-Ratelimit
3. DRF throttles

Example with DRF throttles:

from rest_framework.throttling import UserRateThrottle

class OrderCheckoutThrottle(UserRateThrottle):
    # Limit checkout to 5 per minute per user
    scope = 'checkout'
    
class OrderListThrottle(UserRateThrottle):
    # Limit list view to 30 per minute per user
    scope = 'order_list'

Then in settings.py:
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'order.permissions.OrderCheckoutThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'checkout': '5/min',
        'order_list': '30/min',
    }
}
"""
