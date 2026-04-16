# Multi-Vendor E-Commerce Order System

## Overview

This is a production-ready multi-vendor e-commerce backend using Django Rest Framework. The system allows:

- **Customers** to shop from multiple vendors in a single cart
- **Automatic order splitting** - orders are split by shop during checkout
- **Vendor management** - each vendor sees only their own orders
- **Complete order lifecycle** - from pending → confirmed → shipped → delivered
- **Real-time status tracking** - customers can track orders in real-time
- **Inventory management** - automatic stock reduction on order creation
- **Order timeline** - audit trail of all status changes

## Database Schema

### Models

#### 1. **Order** (Master Order)
Represents a complete purchase by a customer.
```
- user → CustomUser (FK)
- order_number → str (unique, indexed)
- total_amount → decimal (Items + Shipping)
- status → choice (confirmed, pending_payment, cancelled, failed)
- shipping_address, city, upazilla, postal_code, country → str
- phone_number → str (Regex validated: BD numbers)
- payment_method → choice (sslcommerz)
- is_paid → bool (Covers upfront booking fee)
- created_at, updated_at → datetime
```

**Relationships:**
- One Order has many ShopOrders (one per vendor)

#### 2. **ShopOrder** (Vendor-Specific Order)
Represents a single vendor's portion of a master order.
```
- order → Order (FK)
- shop → Shop (FK)
- subtotal → decimal (without fees/tax)
- tax → decimal
- shipping_fee → decimal
- discount → decimal
- total → decimal (subtotal + tax + shipping - discount)
- status → choice (pending, confirmed, processing, shipped, delivered, cancelled, return_requested, returned)
- tracking_number → str
- notes → str
- confirmed_at, shipped_at, delivered_at → datetime
- created_at, updated_at → datetime
```

**Unique Constraint:**
- One shop can have only one ShopOrder per master Order

#### 3. **OrderItem** (Line Items in ShopOrder)
Represents individual products in a vendor's order.
```
- shop_order → ShopOrder (FK)
- product_variant → ProductVariant (FK, PROTECT)
- price_at_purchase → decimal (price snapshot)
- quantity → int (min 1)
- line_total → decimal (calculated: price × quantity)
- status → choice (pending, processing, shipped, delivered, cancelled, returned)
- created_at, updated_at → datetime
```

#### 4. **OrderTimeline** (Audit Trail)
Tracks all status changes and interactions.
```
- shop_order → ShopOrder (FK)
- action → choice (created, confirmed, processing, shipped, delivered, cancelled, payment_processed, return_requested, returned)
- description → str
- created_by → CustomUser (FK, nullable)
- created_at → datetime
```

## Database Indexes

For optimal query performance:
```python
Order:
- (user, -created_at)
- (order_number)

ShopOrder:
- (shop, -created_at)
- (status, -created_at)

OrderItem:
- auto from ForeignKeys
```

## API Endpoints

### Customer Endpoints

#### 1. **Checkout**
```
POST /api/order/checkout/

Request:
{
    "shipping_address": "123 Main Street",
    "shipping_city": "Karachi",
    "shipping_postal_code": "75001",
    "shipping_country": "Pakistan",
    "phone_number": "+92 300 1234567",
    "payment_method": "sslcommerz"
    // or "card", "wallet"
}

Response: 201 Created
{
    "message": "Order created successfully",
    "order": {
        "id": 1,
        "order_number": "ORD-20260407-A1B2C3D4",
        "total_amount": "5000.00",
        "status": "confirmed",
        ...
        "shop_orders": [
            {
                "id": 1,
                "shop_name": "Electronics",
                "total": "3000.00",
                "items": [...]
            },
            {
                "id": 2,
                "shop_name": "Clothing",
                "total": "2000.00",
                "items": [...]
            }
        ]
    }
}
```

#### 2. **List Orders**
```
GET /api/order/list/?status=confirmed&page=1

Response: 200 OK
{
    "count": 25,
    "next": "...",
    "results": [
        {
            "id": 1,
            "order_number": "ORD-20260407-A1B2C3D4",
            "total_amount": "5000.00",
            "status": "confirmed",
            "shop_count": 2,
            "created_at": "2026-04-07T10:30:00Z"
        }
    ]
}
```

#### 3. **Order Details**
```
GET /api/order/{order_id}/

Response: 200 OK
{
    "id": 1,
    "order_number": "ORD-20260407-A1B2C3D4",
    "total_amount": "5000.00",
    "shipping_address": "123 Main Street",
    ...
    "shop_orders": [
        {
            "id": 1,
            "shop_name": "Electronics",
            "total": "3000.00",
            "status": "shipped",
            "tracking_number": "TRK123456",
            "items": [
                {
                    "id": 1,
                    "product_name": "iPhone 15",
                    "product_image": "...",
                    "price_at_purchase": "100000.00",
                    "quantity": 1,
                    "line_total": "100000.00",
                    "status": "shipped"
                }
            ],
            "timeline": [
                {
                    "action": "created",
                    "description": "Order created from cart",
                    "created_at": "2026-04-07T10:30:00Z"
                },
                {
                    "action": "confirmed",
                    "description": "Order confirmed by vendor",
                    "created_at": "2026-04-07T10:35:00Z"
                }
            ]
        }
    ]
}
```

#### 4. **Cancel Order**
```
POST /api/order/shop-order/{shop_order_id}/cancel/

Response: 200 OK
{
    "message": "Order cancelled successfully"
}

Note: Only works for pending or confirmed orders
- Restores product stock
- Records cancellation in timeline
```

### Vendor (Shop Owner) Endpoints

#### 1. **List Shop Orders**
```
GET /api/order/vendor/orders/?status=pending&page=1

Response: 200 OK
{
    "count": 45,
    "results": [
        {
            "id": 1,
            "order_number": "ORD-20260407-A1B2C3D4-15",
            "shop_name": "Electronics",
            "total": "3000.00",
            "status": "pending",
            "item_count": 2,
            "created_at": "2026-04-07T10:30:00Z"
        }
    ]
}
```

#### 2. **Order Details (Vendor View)**
```
GET /api/order/vendor/orders/{shop_order_id}/

Response: 200 OK
{
    "id": 1,
    "order_number": "ORD-20260407-A1B2C3D4-15",
    "customer_name": "Ahmed Khan",
    "customer_phone": "+92 300 1234567",
    "total": "3000.00",
    "status": "pending",
    "items": [
        {
            "id": 1,
            "product_name": "iPhone 15",
            "quantity": 1,
            "price_at_purchase": "150000.00",
            "status": "pending"
        }
    ],
    "timeline": [...]
}
```

#### 3. **Update Order Status**
```
PATCH /api/order/vendor/orders/{shop_order_id}/status/

Request:
{
    "status": "confirmed",
    "tracking_number": "TRK123456",  // optional
    "notes": "Order will be dispatched tomorrow"  // optional
}

Response: 200 OK
{
    "id": 1,
    "status": "confirmed",
    "confirmed_at": "2026-04-07T10:35:00Z",
    ...
}

Valid Status Transitions:
- pending → confirmed, cancelled
- confirmed → processing, cancelled
- processing → shipped, cancelled
- shipped → delivered
- delivered → (end)
- cancelled → (end)
- return_requested → returned, cancelled
- returned → (end)
```

#### 4. **Dashboard Stats**
```
GET /api/order/vendor/stats/

Response: 200 OK
{
    "total_orders": 150,
    "pending_orders": 5,
    "confirmed_orders": 20,
    "shipped_orders": 15,
    "total_sales": 500000.00,
    "average_order_value": 3333.33
}
```

### Review & Rating System

#### 1. **List/Create Reviews**
```
GET /v1/review/?product_id={id}
POST /v1/review/

Request:
{
    "product": 1,
    "rating": "5",
    "review_text": "Excellent product!" // Optional
}
```
**Features:**
- **Purchase Verification**: Users can only review products that have been **delivered** to them.
- **Single Review**: One review per user per product.
- **Automated Comments**: If `review_text` is empty, a default message is generated based on the star rating (e.g., 5-stars → "I am extremely satisfied...").
- **Visual Display**: Returns `rating` (numeric) and `rating_display` (emoji stars: ⭐⭐⭐⭐⭐).

#### 2. **Product Detail Integration**
In `GET /v1/product/{id}/`, the following fields are available:
- `eligibale_for_review`: Boolean indicating if the current logged-in user can leave a review.
- `reviews`: A list of the latest 10 reviews for the product.

#### 3. **Optimized Product Reviews**
```
GET /v1/product/list/{product_id}/product_review/
```
Provides a dedicated, paginated list of all reviews for a specific product.

## Checkout & Payment Flow (Booking Fee + COD)

1. **Cart Preparation** - User adds items; shipping is calculated per shop.
2. **Checkout Initiation** - User provides address/phone (BD mobile validation applies).
3. **Old Order Cleanup** - System automatically cancels the user's previous pending orders and releases their stock.
4. **Stock Locking** - System uses `select_for_update` to lock product rows and `F()` expressions to reserve stock atomically.
5. **Partial Payment Request** - SSLCommerz is initiated for only the **Total Shipping Fee** (Booking Fee).
6. **Payment Gateway** - User pays the Booking Fee.
7. **Webhook/IPN Confirmation** - SSLCommerz notifies our server:
    - Order is marked `confirmed` and `is_paid=True`.
    - **Cart is cleared.**
    - Reserved stock is converted to a permanent deduction.
8. **Fulfillment** - Vendors process orders and collect the remaining item balance via **Cash on Delivery (COD)**.
9. **Failure Handling** - If payment fails or session expires, stock is automatically released back to the inventory.

## Stock Management

Stock is reduced at two points:

1. **Checkout** - Immediately reserved when order created
2. **Cart increment** - Validated before increment (see fixed cart view)

**Important:** If order is cancelled, stock is restored automatically.

## Order Status Flow

### Customer → Vendor View
```
pending (awaiting vendor confirmation)
    ↓
confirmed (vendor accepted)
    ↓
processing (vendor preparing)
    ↓
shipped (in transit with tracking)
    ↓
delivered (completed)
```

### Alternative Paths
```
Any status → cancelled (by customer or vendor)
shipped → return_requested (customer initiated)
return_requested → returned (vendor processed)
```

## Advanced Features

### 1. **Signals** (Automatic Notifications)
- Vendor notified when order received
- Customer notified when status changes
- Timeline automatically recorded

### 2. **Audit Trail** (OrderTimeline)
Every action is logged:
- Who made the change
- What changed
- When it changed
- Why (description)

### 3. **Price Snapshot**
Original prices stored at purchase time:
- Products can change prices later
- Orders always show original prices
- Historical data preserved

### 4. **Volume Discounting** (Future Enhancement)
```python
# In checkout process, after calculating shop totals:
if subtotal > 10000:
    discount = subtotal * 0.05  # 5% discount
elif subtotal > 5000:
    discount = subtotal * 0.03  # 3% discount

shop_order.discount = discount
shop_order.total = subtotal + tax + shipping_fee - discount
```

### 5. **Payment Integration** (Future)
```python
# After order creation, before response:
if payment_method == 'card':
    payment = initiate_payment(order)
    order.is_paid = payment.is_successful
    order.status = 'pending_payment' if not is_paid else 'confirmed'
```

### 6. **Celery Tasks** (Async Jobs)
```python
# Auto-confirm pending orders after 30 minutes
@shared_task
def auto_confirm_pending_orders():
    from datetime import timedelta
    thirty_mins_ago = timezone.now() - timedelta(minutes=30)
    pending = ShopOrder.objects.filter(
        status='pending',
        created_at__lt=thirty_mins_ago
    )
    for order in pending:
        order.status = 'confirmed'
        order.save()

# Send daily digest to vendors
@periodic_task(run_every=crontab(hour=0, minute=0))
def vendor_daily_digest():
    # Send summary of orders from previous day
    pass
```

## Security & Permissions

### Customer Access
- Can only see their own orders
- Can only cancel their own orders
- Enforced by `user=request.user` filter

### Vendor Access
- Can only see orders from their shop
- Enforced by `shop=request.user.shop`
- Only vendors with OneToOneField(shop) allowed

### Admin Only
- Can view all orders
- Can modify statuses manually
- Can access audit trail

## Performance Optimization

### Query Optimization
```python
# Bad
orders = Order.objects.all()
for order in orders:
    for shop_order in order.shop_orders.all():  # N+1 query!
        items = shop_order.items.all()

# Good
orders = Order.objects.prefetch_related(
    'shop_orders__items__product_variant__product__shop'
).all()
```

### Database Indexes
Already configured on:
- `(user, -created_at)` - Fast customer order listing
- `(shop, -created_at)` - Fast vendor order listing
- `(status, -created_at)` - Fast status filtering

### Pagination
All list endpoints return 20 items per page (configurable).

## Testing Recommendations

```python
# tests.py

class CheckoutTestCase(TestCase):
    def test_checkout_creates_multiple_shop_orders(self):
        # Add items from 2 shops to cart
        # Checkout
        # Assert 1 Order with 2 ShopOrders created
        pass
    
    def test_stock_reduced_on_checkout(self):
        # Record initial stock
        # Checkout
        # Assert stock reduced by order quantity
        pass
    
    def test_cart_cleared_after_checkout(self):
        # Checkout
        # Assert cart items deleted
        pass
    
    def test_vendor_can_only_see_own_orders(self):
        # Create orders from 2 vendors
        # Login as vendor 1
        # Assert only vendor 1's orders returned
        pass
    
    def test_invalid_status_transition_rejected(self):
        # Try to go from 'delivered' to 'pending'
        # Assert 400 or error response
        pass
```

## Deployment Checklist

- [ ] Run migrations: `python manage.py migrate`
- [ ] Collect static files: `python manage.py collectstatic`
- [ ] Update settings for email configuration
- [ ] Set up Celery for async tasks
- [ ] Configure CORS for frontend
- [ ] Enable gzip compression
- [ ] Set DEBUG=False in production
- [ ] Configure allowed hosts
- [ ] Set up monitoring/logging
- [ ] Create backups of database
- [ ] Test payment integration
- [ ] Load test with concurrent orders

## Common Issues & Solutions

### Issue: Orders not creating
**Solution:** Check cart has items with valid stock

### Issue: Vendor not seeing orders
**Solution:** Ensure user has OneToOneField(shop) relationship

### Issue: Stock becomes negative
**Solution:** Implement transaction lock on stock field

### Issue: Duplicate order numbers
**Solution:** Already handled with `uuid` in order_number generation

### Issue: Slow order listing
**Solution:** Ensure prefetch_related is used for N+1 queries

## Future Enhancements

1. **Payment Processing** - Stripe/PayPal integration
2. **Refund Management** - Partial/full refunds
3. **Ratings & Reviews** - Post-delivery feedback
4. **Bulk Operations** - Vendor bulk order import
5. **Analytics** - Sales reports, trends
6. **Shipping Integration** - Real-time tracking updates
7. **Multi-currency** - Support different currencies
8. **Subscription Orders** - Recurring purchases
9. **Gift Cards** - Digital gift cards
10. **Return Management** - Full return workflow

## Support & Maintenance

- Monitor OrderTimeline for anomalies
- Review cancelled orders for patterns
- Backup database regularly
- Monitor email delivery
- Test payment gateway regularly
- Load test before peak seasons
