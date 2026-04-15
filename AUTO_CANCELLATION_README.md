# Auto-Order Cancellation System

This system automatically cancels orders that haven't been paid within 1 hour, releasing reserved stock back to inventory.

## How It Works

1. **Order Creation**: When user checks out, stock is RESERVED (not reduced)
2. **Payment Window**: User has 1 hour to complete payment
3. **Auto-Cancellation**: If no payment after 1 hour, order is cancelled and stock is released
4. **Stock Recovery**: Items become available for other customers

## Setup Instructions

### 1. Start Celery Worker
```bash
celery -A core worker --loglevel=info
```

### 2. Start Celery Beat (Scheduler)
```bash
celery -A core beat --loglevel=info
```

### 3. Alternative: Run Manually
```bash
python manage.py cancel_expired_orders
```

### 4. Cron Job (Backup)
Add to crontab for every 15 minutes:
```bash
*/15 * * * * /path/to/venv/bin/python /path/to/project/manage.py cancel_expired_orders
```

## Configuration

**Task Schedule**: Every 15 minutes (configurable in `settings.py`)

**Timeout Period**: 1 hour (configurable in `order/tasks.py`)

**Status Changes**:
- Order: `pending_payment` → `cancelled`
- ShopOrder: `pending` → `cancelled`
- Stock: `reserved_quantity` → released

## Monitoring

Check Celery logs for task execution:
```bash
tail -f celery.log
```

Expected output:
```
[INFO] Auto-cancelled 2 expired orders, released 5 items back to inventory
```

## Files Modified

- `order/tasks.py` - Celery task for auto-cancellation
- `core/settings.py` - Celery Beat schedule configuration
- `order/__init__.py` - Celery app import
- `order/management/commands/cancel_expired_orders.py` - Manual command

## Testing

1. Create an order (stock gets reserved)
2. Wait > 1 hour without payment
3. Run task manually: `python manage.py cancel_expired_orders`
4. Check that stock is released and order is cancelled