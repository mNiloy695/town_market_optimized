# Complete Order Lifecycle & Stock Management

## Overview

The order system follows an **industry-standard two-phase stock management** approach:
1. **Stock Reservation** - At checkout (before payment)
2. **Stock Confirmation** - After payment confirmation

This prevents overselling even if payment fails.

---

## Order Statuses

### Master Order (Order Model)
```
pending_payment → confirmed → cancelled
     ↑              ↓
  checkout      payment_confirmed
```

### Shop Order (ShopOrder Model)
```
pending → confirmed → processing → shipped → delivered
  ↓          ↓           ↓          ↓         ↓
checkout  payment_    vendor_     vendor_   customer
          confirmed   ships       ships     receives
          
Alternative flow:
pending → cancelled (if payment fails)
confirmed → cancelled (customer cancels)
delivered → return_requested → returned (or rejected)
```

---

## Stock Management System

### Field Definitions

**ProductVariant Model:**
```python
stock = IntegerField()                    # Actual available inventory
reserved_quantity = IntegerField(default=0)  # Reserved by pending orders

@property
available_stock:
    return stock - reserved_quantity      # Customers can purchase this
```

### Stock State Changes

```
CHECKOUT
├─ Validate: available_stock >= quantity
├─ Reserve: reserved_quantity += quantity
└─ Stock: unchanged (used in listing)

PAYMENT CONFIRMED
├─ Reduce: stock -= quantity
├─ Release: reserved_quantity -= quantity
└─ Result: both decrease equally, total = stock + reserved

ORDER CANCELLED (pending state)
├─ Release: reserved_quantity -= quantity
└─ Stock: unchanged

ORDER CANCELLED (confirmed state)
├─ Restore: stock += quantity
└─ Release: reserved_quantity -= quantity

RETURN APPROVED
├─ Restore: stock += quantity
└─ Quantity reuses inventory
```

---

## Complete Workflow

### Phase 1: Checkout (Before Payment)

**Endpoint:** `POST /order/checkout/`

**Request:**
```json
{
    "shipping_address": "123 Main St",
    "shipping_city": "Karachi",
    "shipping_postal_code": "75001",
    "shipping_country": "Pakistan",
    "phone_number": "+92 300 1234567",
    "payment_method": "cash_on_delivery"
}
```

**What Happens:**
1. Validate cart is not empty
2. Validate `available_stock >= quantity` for each item
3. **Create Order** with status `pending_payment`, `is_paid=False`
4. **Group cart items by shop** - create separate ShopOrder for each vendor
5. **For each OrderItem:**
   - Price snapshot: store `price_at_purchase`
   - **Reserve stock**: `reserved_quantity += quantity`
   - Do NOT reduce actual `stock` yet
6. Clear customer's cart
7. Return Order with all ShopOrders

**Response:**
```json
{
    "message": "Order created successfully",
    "order": {
        "id": 1,
        "order_number": "ORD-20260407-ABC12345",
        "status": "pending_payment",
        "is_paid": false,
        "total_amount": "5000.00",
        "shop_orders": [
            {
                "id": 1,
                "status": "pending",
                "total": "2500.00",
                "items": [
                    {
                        "product_variant": 1,
                        "quantity": 2,
                        "price_at_purchase": "1250.00",
                        "line_total": "2500.00"
                    }
                ]
            }
        ]
    }
}
```

**Stock State After Checkout:**
```
ProductVariant:
  stock: 100
  reserved_quantity: 2
  available_stock: 98
  
Next customer cannot purchase these 2 items until:
- Payment confirmed (becomes actual stock deduction)
- Order cancelled (reservation released)
- Auto-cancelled after 1 hour (reservation released)
```

---

### Phase 2: Payment Processing

**External Payment Gateway**
- Customer completes payment with Stripe, JazzCash, etc.
- Payment processor returns `payment_id` and transaction status

---

### Phase 3: Payment Confirmation

**Endpoint:** `POST /order/{order_id}/confirm-payment/`

**Request:**
```json
{
    "payment_id": "pay_1234567890",
    "payment_proof": "optional_reference_number"
}
```

**What Happens:**
1. Validate Order exists and belongs to customer
2. Check Order status is `pending_payment`
3. Check Order is not already paid
4. **Call Order.confirm_payment():**
   - Set `is_paid = True`, status = `confirmed`
   - For each ShopOrder in status `pending`:
     - **Reduce actual stock**: `stock -= quantity`
     - **Release reservation**: `reserved_quantity -= quantity`
     - Update ShopOrder status: `pending → confirmed`
     - Set `confirmed_at = now()`
     - Add timeline entry: "Payment confirmed - stock secured"

**Response:**
```json
{
    "message": "Payment confirmed successfully",
    "order": {
        "id": 1,
        "status": "confirmed",
        "is_paid": true,
        "shop_orders": [
            {
                "id": 1,
                "status": "confirmed",
                "confirmed_at": "2026-04-07T10:30:00Z"
            }
        ]
    },
    "next_step": "Vendors are processing your order"
}
```

**Stock State After Payment Confirmation:**
```
ProductVariant:
  stock: 98           (reduced from 100)
  reserved_quantity: 0
  available_stock: 98
  
These items are now locked in inventory - 
vendor MUST fulfill them.
```

---

### Phase 4: Vendor Order Processing & Fulfillment

**Endpoint:** `PATCH /order/vendor/orders/{shop_order_id}/status/`

**Why Verification is NOT needed:**
- Stock is already locked at payment confirmation
- Vendor is guaranteed items are in inventory
- No overselling possible

**Status Transitions:**

#### 4.1 Vendor Confirms Order (Optional)
**Request:**
```json
{
    "status": "confirmed"
}
```
- Vendor acknowledges receipt and readiness
- Typically skipped if vendor auto-processes
- Add timeline entry: "Order Confirmed"

#### 4.2 Vendor Processes & Ships Order
**Request:**
```json
{
    "status": "processing"
}
```
- Vendor internally picks & packs items (warehouse operation)
- Stock already verified - no re-validation needed
- Add timeline entry: "Processing Started"

#### 4.3 Mark Order as Shipped
**Request:**
```json
{
    "status": "shipped",
    "tracking_number": "TRK-1234567890"
}
```
- Set `shipped_at = now()`
- Store tracking number for customer
- Customer receives shipping notification
- Add timeline entry: "Shipped with tracking"

#### 4.4 Mark Order as Delivered
**Request (from system or vendor):**
```json
{
    "status": "delivered"
}
```
- Set `delivered_at = now()`
- Order complete - customer can now request return
- Add timeline entry: "Delivered"

---

### Phase 5: Returns & Refunds (Optional)

#### 5.1 Customer Requests Return

**Endpoint:** `POST /order/shop-order/{shop_order_id}/return/`

**Request:**
```json
{
    "reason": "Item was damaged",
    "product_condition": "opened_but_unused"
}
```

**Requirements:**
- Order must be in `delivered` status
- Return period must be within policy (e.g., 30 days)

**What Happens:**
1. Update ShopOrder status: `delivered → return_requested`
2. Add timeline entry: "Return requested - awaiting vendor approval"
3. Notify vendor with reason

**Response:**
```json
{
    "message": "Return request submitted",
    "order": {
        "status": "return_requested",
        "timeline": [
            {
                "action": "return_requested",
                "description": "Return requested. Reason: Item was damaged"
            }
        ]
    }
}
```

#### 5.2 Vendor Approves/Rejects Return

**Endpoint:** `PATCH /order/vendor/orders/{shop_order_id}/return-approval/`

**5.2.1 Approve Return:**
**Request:**
```json
{
    "action": "approve"
}
```

**What Happens:**
1. **Restore stock**: `stock += quantity`
2. Update status: `return_requested → returned`
3. Process refund via payment gateway
4. Add timeline entry: "Return approved - refund processed"
5. Customer receives refund within 3-5 business days

**Response:**
```json
{
    "message": "Return approved and stock restored",
    "order": {
        "status": "returned"
    }
}
```

**Stock State After Approval:**
```
ProductVariant:
  stock: 100          (restored)
  reserved_quantity: 0
  
Item is now available for other customers again.
```

**5.2.2 Reject Return:**
**Request:**
```json
{
    "action": "reject",
    "reason": "Item appears to be used"
}
```

**What Happens:**
1. Revert status: `return_requested → delivered`
2. Keep stock unchanged
3. Add timeline entry: "Return rejected - Item was used"
4. No refund processed

---

### Phase 6: Order Cancellation (If Payment Fails)

**Endpoint:** `POST /order/shop-order/{shop_order_id}/cancel/`

**Scenario 1: Cancel Before Payment Confirmation (status: pending)**
```
if order.status == 'pending':
    # Release reserved stock only
    reserved_quantity -= quantity
    stock remains unchanged
```

**Scenario 2: Cancel After Payment Confirmation (status: confirmed)**
```
if order.status == 'confirmed':
    # Refund payment
    # Restore to inventory
    stock += quantity
    reserved_quantity -= quantity
```

**What Happens for Both:**
1. Update status: `pending/confirmed → cancelled`
2. Release/restore stock appropriately
3. Add timeline entry: "Order cancelled by customer"
4. If paid: initiate refund
5. Notify vendor

**Response:**
```json
{
    "message": "Order cancelled successfully",
    "refund": {
        "amount": "2500.00",
        "status": "processing",
        "estimated_arrival": "3-5 business days"
    }
}
```

---

## Timeout Handling

**Auto-Release Pending Orders** (1 hour)

Celery task runs every 15 minutes:
```python
# Find orders older than 1 hour
expired_orders = Order.objects.filter(
    status='pending_payment',
    created_at__lt=timezone.now() - timedelta(hours=1),
    is_paid=False
)

# Cancel orders and release reserved stock
for order in expired_orders:
    # Release reservations: reserved_quantity -= quantity
    # Cancel shop orders: status = 'cancelled'
    # Add timeline: 'Order auto-cancelled due to payment timeout'
```

**Alternative: Manual Command**
```bash
python manage.py cancel_expired_orders
```

**Cron Job Example:**
```bash
*/15 * * * * /path/to/venv/bin/python /path/to/project/manage.py cancel_expired_orders
```

---

## API Endpoints Reference

### Customer Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/order/checkout/` | Create order from cart |
| GET | `/order/list/` | List all customer orders |
| GET | `/order/{order_id}/` | Get order details |
| POST | `/order/{order_id}/confirm-payment/` | Confirm payment |
| POST | `/order/shop-order/{shop_order_id}/cancel/` | Cancel order |
| POST | `/order/shop-order/{shop_order_id}/return/` | Request return |

### Vendor Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/order/vendor/orders/` | List vendor's orders |
| GET | `/order/vendor/orders/{shop_order_id}/` | Get order details |
| PATCH | `/order/vendor/orders/{shop_order_id}/status/` | Update order status |
| PATCH | `/order/vendor/orders/{shop_order_id}/return-approval/` | Approve/reject return |
| GET | `/order/vendor/stats/` | Dashboard statistics |

---

## Error Handling

### Insufficient Stock
```json
{
    "error": "Not enough stock for Nike Air Max Professional",
    "available": 2,
    "requested": 5
}
```

### Invalid Order Status
```json
{
    "error": "Order is already confirmed - cannot cancel",
    "current_status": "confirmed"
}
```

### Unauthorized Access
```json
{
    "error": "You don't have permission to access this order"
}
```

---

## Timeline Events

All status changes are recorded:

```python
TIMELINE_ACTIONS = [
    ('created', 'Order Created'),
    ('confirmed', 'Order Confirmed'),
    ('processing', 'Processing Started'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
    ('payment_processed', 'Payment Processed'),
    ('return_requested', 'Return Requested'),
    ('returned', 'Item Returned'),
]
```

Example timeline:
```json
{
    "timeline": [
        {
            "action": "created",
            "description": "Order created from cart",
            "created_at": "2026-04-07T10:00:00Z",
            "created_by": "customer@example.com"
        },
        {
            "action": "payment_processed",
            "description": "Payment confirmed - stock secured",
            "created_at": "2026-04-07T10:15:00Z"
        },
        {
            "action": "confirmed",
            "description": "Order Confirmed by vendor",
            "created_at": "2026-04-07T10:20:00Z",
            "created_by": "vendor@shop.com"
        },
        {
            "action": "processing",
            "description": "Processing Started",
            "created_at": "2026-04-07T11:00:00Z"
        },
        {
            "action": "shipped",
            "description": "Shipped with tracking TRK-123",
            "created_at": "2026-04-07T14:00:00Z"
        },
        {
            "action": "delivered",
            "description": "Delivered",
            "created_at": "2026-04-07T16:00:00Z"
        }
    ]
}
```

---

## Database Relationships

```
Order (1)
├── ShopOrder (many)
│   ├── OrderItem (many)
│   │   └── ProductVariant
│   └── OrderTimeline (many)
└── Cart Items ← (cleared after checkout)

ProductVariant
├── stock (actual inventory - reduces after payment)
├── reserved_quantity (pending orders - releases after payment or cancellation)
├── price (current price for new orders)
└── order_items ← (historical price snapshots)
```

---

## Best Practices

1. **Always use `available_stock` for listing** - Don't show stock that's reserved
2. **Use `transaction.atomic()`** - All stock changes must be atomic
3. **Log all state changes** - OrderTimeline tracks everything
4. **Validate before action** - Check status before updating
5. **Handle race conditions** - Use database-level constraints for unique_together
6. **Notify customers** - Send email/SMS for all status changes
7. **Test cancellations** - Both pending and confirmed cancellations
8. **Implement timeout** - Auto-release pending orders after 24 hours

---

## Testing Scenarios

### Success Path
1. Checkout → pending_payment, stock reserved
2. Confirm payment → confirmed, stock reduced
3. Vendor processes → processing
4. Vendor ships → shipped
5. Delivered → delivered

### Cancellation Path
1. Checkout → pending_payment, stock reserved
2. Customer cancels → reserved_quantity released
3. Next customer can now order

### Payment Failure Path
1. Checkout → pending_payment, stock reserved
2. Payment failed → order stays pending_payment
3. After 1 hour → auto-cancelled, stock released
4. Next customer can now order

### Return Path
1. Order delivered
2. Customer requests return
3. Vendor approves → stock restored
4. Refund processed

---

## Integration Points

### Payment Gateway
- Call `/order/{order_id}/confirm-payment/` after successful payment
- Include payment transaction ID
- Handle webhook for async payment confirmation

### Notification Service
- Send email on every status change
- SMS for important milestones (confirmed, shipped, delivered)
- Push notifications for app users

### Inventory Management
- Monitor `available_stock` for reordering
- Alert vendor when stock falls below threshold
- Auto-disable variant if `available_stock <= 0`

### Analytics
- Track conversion rate: checkout → payment_confirmed
- Track cancellation rate by status
- Monitor return rate
- Analyze refund costs

---

## FAQ

**Q: Why reserve stock at checkout instead of reducing immediately?**
A: Because many customers abandon carts or fail payment. Reserving ensures accurate inventory without locking up stock prematurely.

**Q: What if customer never completes payment?**
A: After 24 hours, a background job auto-cancels the order and releases the reservation.

**Q: Can customer modify order after checkout?**
A: No, stock is already reserved. They must cancel and create new order.

**Q: What happens if vendor rejects return?**
A: Order reverts to "delivered" status, customer keeps item and stock is not restored.

**Q: Can order be cancelled after shipped?**
A: No, only pending and confirmed orders can be cancelled. After shipped, customer must request return.

