# Quick Reference Guide - Multi-Vendor Order System

## File Structure

```
order/
├── __init__.py
├── models.py                     # ✅ UPDATED - Order, ShopOrder, OrderItem, OrderTimeline
├── serializers.py               # ✅ NEW - All DRF serializers
├── views.py                      # ✅ UPDATED - All API endpoints
├── urls.py                       # ✅ UPDATED - URL routing
├── signals.py                    # ✅ UPDATED - Event handlers
├── permissions.py               # ✅ NEW - Custom permissions
├── admin.py                      # ✅ UPDATED - Django admin config
├── apps.py                       # ✅ UPDATED - App configuration
├── migrations/
│   ├── 0001_initial.py          # Will be created by makemigrations
│   └── ...
└── tests.py                      # Examples in integration guide

Documentation:
├── ORDER_SYSTEM_DOCUMENTATION.md          # Complete system docs
├── ORDER_SYSTEM_INTEGRATION_GUIDE.md      # Setup & testing guide
├── ORDER_SYSTEM_HELPERS.py               # Utility classes & examples
└── ORDER_SYSTEM_IMPLEMENTATION_SUMMARY.md # Implementation summary
```

## Most Important Files to Review

### 1. **order/models.py** ⭐⭐⭐
The heart of the system. Defines:
- Order - Master order
- ShopOrder - Vendor-specific order
- OrderItem - Line items
- OrderTimeline - Audit trail

Key relationships:
```
Order (1) ──→ (many) ShopOrder (1) ──→ (many) OrderItem
                  ↓
               Shop (vendor)
                  ↓
           ProductVariant (stock managed here)
```

### 2. **order/serializers.py** ⭐⭐⭐
DRF serializers that handle:
- Input validation (CheckoutSerializer)
- Output formatting (OrderDetailSerializer, ShopOrderListSerializer)
- Status transitions (ShopOrderStatusUpdateSerializer)

### 3. **order/views.py** ⭐⭐⭐
All API endpoints:
- Checkout logic (splits by shop)
- Customer order access
- Vendor order access
- Status updates with validation

### 4. **order/permissions.py** ⭐⭐
Security layer:
- IsCustomer - Customers see own orders only
- IsVendor - Vendors see own shop's orders only
- CanCancelOrder - Only pending/confirmed can be cancelled

## Quick Test Checklist

✅ Run migrations:
```bash
python manage.py makemigrations order
python manage.py migrate
```

✅ Check models created:
```bash
python manage.py shell
>>> from order.models import Order, ShopOrder, OrderItem
>>> Order.objects.all()  # Should work
```

✅ Check admin:
```
http://localhost:8000/admin/order/
```

✅ Test checkout:
```bash
# 1. Ensure cart has items from 2+ shops
# 2. POST /api/order/checkout/
# 3. Verify:
#    - 1 Order created
#    - 2 ShopOrders created (one per shop)
#    - Stock reduced
#    - Cart cleared
```

✅ Test vendor access:
```bash
# 1. Login as vendor
# 2. GET /api/order/vendor/orders/
# 3. Should see only vendor's orders
```

## Key Concepts

### Order Flow
```
1. Customer adds items from Shop-A and Shop-B to cart
2. Calls checkout API
3. System groups items: Shop-A items, Shop-B items
4. Creates 1 Order linking to customer
5. Creates 2 ShopOrders (one per shop)
6. Creates OrderItems under each ShopOrder
7. Reduces stock for each item
8. Clears cart
9. Returns complete order structure
```

### Stock Management
```
Before Checkout: iPhone stock = 100
After Checkout (2 units ordered): iPhone stock = 98

If order cancelled: iPhone stock = 100 (restored)
If order returned: iPhone stock = 100 (restored)
```

### Permission Model
```
Customer:
- GET /order/list/ → Only gets own orders
- GET /order/{id}/ → Can only access own order
- POST /order/checkout/ → Creates order under their account
- POST /order/.../cancel/ → Can cancel only pending/confirmed

Vendor:
- GET /vendor/orders/ → Only gets orders from their shop
- PATCH /vendor/orders/{id}/status/ → Can update only their shop's orders
- GET /vendor/stats/ → Analytics for their shop only

Admin:
- Can see everything in /admin/
```

## Common Operations

### Checkout
```python
POST /api/order/checkout/
{
    "shipping_address": "123 Main",
    "shipping_city": "Karachi",
    "shipping_postal_code": "75001",
    "shipping_country": "Pakistan",
    "phone_number": "+92 300 1234567",
    "payment_method": "sslcommerz"
}

Response:
{
    "order": {
        "id": 1,
        "order_number": "ORD-20260407-ABC12345",
        "total_amount": "5000.00",
        "shop_orders": [
            {"id": 1, "shop_name": "Electronics", "total": "3000.00", ...},
            {"id": 2, "shop_name": "Clothing", "total": "2000.00", ...}
        ]
    }
}
```

### Vendor Update Status
```python
PATCH /api/order/vendor/orders/1/status/
{
    "status": "confirmed",
    "tracking_number": "TRK123456",
    "notes": "Will ship tomorrow"
}

Valid transitions:
pending → confirmed, cancelled
confirmed → processing, cancelled
processing → shipped
shipped → delivered
delivered → (end)
cancelled → (end)
returned → (end)
```

### Analytics for Vendor
```python
GET /api/order/vendor/stats/

Response:
{
    "total_orders": 150,
    "pending_orders": 5,
    "confirmed_orders": 20,
    "shipped_orders": 15,
    "total_sales": "500000.00",
    "average_order_value": "3333.33"
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "User does not own a shop" | Ensure vendor has OneToOneField(Shop) relationship |
| Checkout fails with empty cart | Add items to cart first |
| Vendor can't see orders | Verify vendor owns the shop, check permissions |
| Stock not reducing | Check OrderItem quantities, verify save() called |
| Can't update order status | Check status transition is valid, user owns shop |

## Database Schema Quick Reference

### Order Table
```
id (PK)
user_id (FK → CustomUser)
order_number (UNIQUE, indexed)
total_amount
status (confirmed, pending_payment, cancelled)
payment_method
is_paid
shipping_address, city, postal_code, country
phone_number
created_at (indexed), updated_at
```

### ShopOrder Table
```
id (PK)
order_id (FK → Order)
shop_id (FK → Shop, indexed)
subtotal, tax, shipping_fee, discount, total
status (pending, confirmed, processing, shipped, delivered, cancelled, return_requested, returned, indexed)
tracking_number, notes
confirmed_at, shipped_at, delivered_at
created_at (indexed), updated_at
UNIQUE(order_id, shop_id)
```

### OrderItem Table
```
id (PK)
shop_order_id (FK → ShopOrder)
product_variant_id (FK → ProductVariant, PROTECT)
price_at_purchase
quantity (min 1)
line_total (calculated: price × qty)
status (pending, processing, shipped, delivered, cancelled, returned)
created_at, updated_at
```

### OrderTimeline Table
```
id (PK)
shop_order_id (FK → ShopOrder, indexed)
action (created, confirmed, processing, shipped, delivered, cancelled, payment_processed, return_requested, returned)
description
created_at (indexed), created_by_id (FK → CustomUser, nullable)
```

## Performance Tips

1. **Always use prefetch_related** for orders with items:
```python
orders = Order.objects.prefetch_related('shop_orders__items')
```

2. **Use select_related** for foreign keys:
```python
shop_orders = ShopOrder.objects.select_related('shop__owner', 'order__user')
```

3. **Index on frequently filtered fields**: Done ✅

4. **Paginate large result sets**: Implemented ✅

5. **Cache vendor stats** if called frequently

## Extending the System

### Add Coupon Support
Modify CheckoutSerializer to accept coupon_code:
```python
coupon_code = serializers.CharField(required=False)
```

Then in checkout logic:
```python
discount = apply_coupon(coupon_code, subtotal)
shop_order.discount = discount
```

### Add Payment Integration
In CheckoutView.post():
```python
payment = PaymentGateway.initiate_payment(order, payment_method)
if payment['success']:
    order.is_paid = True
else:
    order.status = 'pending_payment'
```

### Add Email Notifications
Already set up in signals.py - just uncomment and configure:
```python
send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
```

### Add Celery Tasks
Example in ORDER_SYSTEM_HELPERS.py for:
- Auto-confirm orders after timeout
- Daily digest emails
- Return expiry checks

## Support & Help

- 📖 Read ORDER_SYSTEM_DOCUMENTATION.md for complete details
- 🧪 Check ORDER_SYSTEM_INTEGRATION_GUIDE.md for testing
- 🛠️ Use examples in ORDER_SYSTEM_HELPERS.py for custom logic
- 📝 Review test cases in integration guide for usage patterns
