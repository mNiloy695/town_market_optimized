# Order System - Integration & Testing Guide

## Quick Start

### 1. Run Migrations

```bash
# Create migration files
python manage.py makemigrations

# Apply migrations to database
python manage.py migrate
```

### 2. Update Settings (if needed)

In `core/settings.py`, ensure:

```python
# Email configuration (for notifications)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-email-provider.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'noreply@yourapp.com'

# REST Framework pagination
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Installed apps (should already be there)
INSTALLED_APPS = [
    ...
    'rest_framework',
    'order',
    'cart',
    'product',
    'shop',
    'accounts',
    ...
]
```

### 3. Include Order URLs

In `core/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/order/', include('order.urls')),  # Add this line
    path('api/cart/', include('cart.urls')),
    path('api/product/', include('product.urls')),
    path('api/shop/', include('shop.urls')),
    path('api/accounts/', include('accounts.urls')),
]
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
# Then visit: http://localhost:8000/admin/
```

## Testing the API

### Using cURL

```bash
# Checkout
curl -X POST http://localhost:8000/api/order/checkout/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shipping_address": "123 Main Street",
    "shipping_city": "Karachi",
    "shipping_postal_code": "75001",
    "shipping_country": "Pakistan",
    "phone_number": "+92 300 1234567",
    "payment_method": "cash_on_delivery"
  }'

# List orders
curl -X GET http://localhost:8000/api/order/list/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get order details
curl -X GET http://localhost:8000/api/order/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Vendor: List orders
curl -X GET http://localhost:8000/api/order/vendor/orders/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Vendor: Update order status
curl -X PATCH http://localhost:8000/api/order/vendor/orders/1/status/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "confirmed",
    "tracking_number": "TRK123456"
  }'
```

### Using Postman

1. Import the provided Postman collection
2. Set base URL: `http://localhost:8000`
3. Add Bearer token to authorization
4. Test endpoints one by one

### Using Python Requests

```python
import requests
import json

# Authentication
token = 'your-auth-token'
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Checkout
checkout_data = {
    "shipping_address": "123 Main Street",
    "shipping_city": "Karachi",
    "shipping_postal_code": "75001",
    "shipping_country": "Pakistan",
    "phone_number": "+92 300 1234567",
    "payment_method": "cash_on_delivery"
}

response = requests.post(
    'http://localhost:8000/api/order/checkout/',
    json=checkout_data,
    headers=headers
)

order = response.json()
print(f"Order created: {order['order']['order_number']}")
print(f"Total shops: {len(order['order']['shop_orders'])}")

# List orders
response = requests.get(
    'http://localhost:8000/api/order/list/',
    headers=headers
)
orders = response.json()
print(f"Total orders: {orders['count']}")

# Vendor: Update order status
vendor_update = {
    "status": "confirmed",
    "tracking_number": "TRK123456",
    "notes": "Order will be dispatched tomorrow"
}

response = requests.patch(
    'http://localhost:8000/api/order/vendor/orders/1/status/',
    json=vendor_update,
    headers=headers
)
print(response.json())
```

## Unit Tests

Create `order/tests.py`:

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal

from cart.models import Cart, CartItem
from order.models import Order, ShopOrder, OrderItem
from product.models import Product, ProductVariant
from shop.models import Shop

User = get_user_model()

class CheckoutTestCase(TestCase):
    """Test checkout functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create users
        self.customer = User.objects.create_user(
            phone='+92 300 1111111',
            country_code='PK',
            name='Test Customer',
            password='testpass123'
        )
        
        self.vendor = User.objects.create_user(
            phone='+92 300 2222222',
            country_code='PK',
            name='Test Vendor',
            password='testpass123'
        )
        
        # Create shop
        from shop.models import Market
        market = Market.objects.create(name='Test Market', address='Test Address')
        self.shop = Shop.objects.create(
            name='Test Shop',
            owner=self.vendor,
            market=market,
            address='Shop Address'
        )
        
        # Create product and variant
        from product.models import ProductCategory, ParentProductCategory
        parent_cat = ParentProductCategory.objects.create(name='Electronics')
        category = ProductCategory.objects.create(name='Phones', parent=parent_cat)
        
        self.product = Product.objects.create(
            name='Test Phone',
            shop=self.shop,
            sub_category=category
        )
        
        self.variant = ProductVariant.objects.create(
            product=self.product,
            price=Decimal('50000.00'),
            stock=10,
            description='Test variant'
        )
        
        # Create cart
        self.cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(
            cart=self.cart,
            product_variant=self.variant,
            quantity=2
        )
    
    def test_checkout_creates_order(self):
        """Test that checkout creates an order"""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Order.objects.exists())
    
    def test_checkout_creates_shop_order(self):
        """Test that checkout creates a shop order"""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ShopOrder.objects.filter(shop=self.shop).exists())
    
    def test_checkout_reduces_stock(self):
        """Test that checkout reduces product stock"""
        initial_stock = self.variant.stock
        
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, initial_stock - 2)
    
    def test_checkout_clears_cart(self):
        """Test that checkout clears the cart"""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.items.count(), 0)
    
    def test_checkout_empty_cart_fails(self):
        """Test that checkout fails with empty cart"""
        self.cart.items.all().delete()
        
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_checkout_insufficient_stock_fails(self):
        """Test that checkout fails with insufficient stock"""
        CartItem.objects.filter(cart=self.cart).update(quantity=100)
        
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_address': '123 Main Street',
            'shipping_city': 'Karachi',
            'shipping_postal_code': '75001',
            'shipping_country': 'Pakistan',
            'phone_number': '+92 300 1234567',
            'payment_method': 'cash_on_delivery'
        }
        
        response = self.client.post('/api/order/checkout/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OrderListTestCase(TestCase):
    """Test order list functionality"""
    
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            phone='+92 300 1111111',
            country_code='PK',
            name='Test Customer',
            password='testpass123'
        )
    
    def test_customer_can_only_see_own_orders(self):
        """Test that customers can only see their own orders"""
        other_customer = User.objects.create_user(
            phone='+92 300 3333333',
            country_code='PK',
            name='Other Customer',
            password='testpass123'
        )
        
        # Create orders for both
        Order.objects.create(user=self.customer, total_amount=1000)
        Order.objects.create(user=other_customer, total_amount=2000)
        
        self.client.force_authenticate(user=self.customer)
        response = self.client.get('/api/order/list/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class VendorOrderTestCase(TestCase):
    """Test vendor order management"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create vendor
        self.vendor = User.objects.create_user(
            phone='+92 300 2222222',
            country_code='PK',
            name='Test Vendor',
            password='testpass123'
        )
        
        # Create shop
        from shop.models import Market
        market = Market.objects.create(name='Test Market', address='Test Address')
        self.shop = Shop.objects.create(
            name='Test Shop',
            owner=self.vendor,
            market=market,
            address='Shop Address'
        )
        
        # Create customer
        self.customer = User.objects.create_user(
            phone='+92 300 1111111',
            country_code='PK',
            name='Test Customer',
            password='testpass123'
        )
        
        # Create order
        self.order = Order.objects.create(
            user=self.customer,
            total_amount=5000
        )
        
        self.shop_order = ShopOrder.objects.create(
            order=self.order,
            shop=self.shop,
            subtotal=5000,
            total=5000
        )
    
    def test_vendor_can_update_order_status(self):
        """Test that vendor can update order status"""
        self.client.force_authenticate(user=self.vendor)
        
        data = {'status': 'confirmed'}
        response = self.client.patch(
            f'/api/order/vendor/orders/{self.shop_order.id}/status/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.shop_order.refresh_from_db()
        self.assertEqual(self.shop_order.status, 'confirmed')
    
    def test_vendor_cannot_see_other_shop_orders(self):
        """Test that vendor can only see their own orders"""
        other_vendor = User.objects.create_user(
            phone='+92 300 4444444',
            country_code='PK',
            name='Other Vendor',
            password='testpass123'
        )
        
        other_market = Market.objects.create(name='Other Market', address='Other Address')
        other_shop = Shop.objects.create(
            name='Other Shop',
            owner=other_vendor,
            market=other_market,
            address='Other Address'
        )
        
        other_shop_order = ShopOrder.objects.create(
            order=self.order,
            shop=other_shop,
            subtotal=2000,
            total=2000
        )
        
        self.client.force_authenticate(user=self.vendor)
        response = self.client.get('/api/order/vendor/orders/')
        
        # Should only see the vendor's own shop order
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.shop_order.id)


# ============================================================================
# INTEGRATION TEST
# ============================================================================

class E2EOrderFlowTestCase(TestCase):
    """End-to-end order flow test"""
    
    def test_complete_order_flow(self):
        """Test complete order flow from cart to delivery"""
        # This is a simplified example of E2E testing
        # In practice, you'd test the entire flow with multiple steps
        pass
```

Run tests with:
```bash
python manage.py test order
python manage.py test order.tests.CheckoutTestCase
python manage.py test order.tests.CheckoutTestCase.test_checkout_creates_order
```

## Performance Testing

```bash
# Install locust for load testing
pip install locust

# Create locustfile.py
# Run: locust -f locustfile.py --host=http://localhost:8000
```

## Database Optimization

```sql
-- Check index sizes
SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_indexes
JOIN pg_class ON indexname = relname
ORDER BY pg_relation_size(indexrelid) DESC;

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM order_order WHERE user_id = 1 ORDER BY created_at DESC;
```

## Deployment Checklist

- [ ] Run `python manage.py migrate`
- [ ] Run `python manage.py collectstatic`
- [ ] Test all API endpoints
- [ ] Test with production data volume
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Configure email backend
- [ ] Test payment gateway
- [ ] Set up backups
- [ ] Configure CDN for images
- [ ] Enable caching
- [ ] Monitor performance metrics

## Troubleshooting

### Issue: "User does not own a shop"
**Solution:** Ensure the OneToOneField(shop) is set for the vendor user.

### Issue: Orders not visible
**Solution:** Check user and shop relationships are correct. Use Django shell to verify.

### Issue: Stock becoming negative
**Solution:** Wrap checkout in transaction with row-level locking.

### Issue: Slow checkout
**Solution:** Optimize queries with `select_related` and `prefetch_related`.

### Issue: Email not sending
**Solution:** Configure EMAIL_* settings and test with `python manage.py shell`:
```python
from django.core.mail import send_mail
send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

## Support

For issues or questions:
1. Check the documentation
2. Review the code comments
3. Check test cases for usage examples
4. Enable DEBUG mode and check console output
