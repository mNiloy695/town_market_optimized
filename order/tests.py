from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal

from shop.models import Market, Shop, Category
from product.models import ParentProductCategory, ProductCategory, Product, ProductVariant
from order.models import Order, ShopOrder, OrderItem

User = get_user_model()

class OrderCancellationTests(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            phone="01712345678",
            country_code="BD",
            password="testpassword123",
            name="Test Customer"
        )
        
        # Create vendor user
        self.vendor_user = User.objects.create_user(
            phone="01711111111",
            country_code="BD",
            password="testpassword123",
            name="Test Vendor"
        )

        # Create market
        self.market = Market.objects.create(
            name="Test Market",
            address="Test Address"
        )

        # Create category
        self.category = Category.objects.create(
            name="Test Category",
            slug="test-category"
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            address="Test Shop Address",
            market=self.market,
            owner=self.vendor_user,
            status="approved"
        )
        self.shop.Category.add(self.category)

        # Create product category
        self.parent_cat = ParentProductCategory.objects.create(name="Parent Cat")
        self.prod_cat = ProductCategory.objects.create(name="Product Cat", parent=self.parent_cat)

        # Create product
        self.product = Product.objects.create(
            name="Test Product",
            shop=self.shop,
            sub_category=self.prod_cat
        )

        # Create product variant
        self.variant = ProductVariant.objects.create(
            product=self.product,
            price=Decimal("150.00"),
            stock=10,
            reserved_quantity=0
        )

    def test_cancel_pending_payment_order_releases_reservation(self):
        """
        An order in 'pending_payment' status should always be cancellable.
        Cancelling it should release the reserved quantity.
        """
        # Create order
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="pending_payment",
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )

        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="pending",
            subtotal=Decimal("150.00"),
            total=Decimal("150.00")
        )

        OrderItem.objects.create(
            shop_order=shop_order,
            product_variant=self.variant,
            quantity=2,
            price_at_purchase=Decimal("150.00")
        )

        # Simulating checkout reservation
        self.variant.reserved_quantity = 2
        self.variant.save()

        # Perform cancellation
        success, message = order.cancel_order(reason="Customer cancelled")
        self.assertTrue(success)
        self.assertEqual(message, "Order cancelled successfully")

        # Reload objects
        order.refresh_from_db()
        shop_order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(shop_order.status, "cancelled")
        self.assertEqual(self.variant.reserved_quantity, 0)
        self.assertEqual(self.variant.stock, 10)

    def test_cancel_confirmed_order_within_20_minutes_restores_stock(self):
        """
        A confirmed order should be cancellable within 20 minutes of confirmation.
        Cancelling it should restore the variant's actual stock, but not touch reserved_quantity.
        """
        # Create confirmed order
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )

        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="confirmed",
            confirmed_at=timezone.now(),
            subtotal=Decimal("150.00"),
            total=Decimal("150.00")
        )

        OrderItem.objects.create(
            shop_order=shop_order,
            product_variant=self.variant,
            quantity=2,
            price_at_purchase=Decimal("150.00")
        )

        # Since payment is confirmed, actual stock is reduced and reservation released.
        self.variant.stock = 8
        self.variant.reserved_quantity = 0
        self.variant.save()

        # Perform cancellation
        success, message = order.cancel_order(reason="Customer cancelled within 20 min")
        self.assertTrue(success)

        # Reload objects
        order.refresh_from_db()
        shop_order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(shop_order.status, "cancelled")
        self.assertEqual(self.variant.stock, 10)  # Stock restored to 10
        self.assertEqual(self.variant.reserved_quantity, 0)  # Reserved quantity untouched

    def test_cancel_confirmed_order_after_20_minutes_fails(self):
        """
        A confirmed order cannot be cancelled after 20 minutes of confirmation.
        It should return the exact error message specified in requirements.
        """
        # Create order confirmed 25 minutes ago
        confirmed_time = timezone.now() - timedelta(minutes=25)
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            confirmed_at=confirmed_time,
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )

        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="confirmed",
            confirmed_at=confirmed_time,
            subtotal=Decimal("150.00"),
            total=Decimal("150.00")
        )

        OrderItem.objects.create(
            shop_order=shop_order,
            product_variant=self.variant,
            quantity=2,
            price_at_purchase=Decimal("150.00")
        )

        self.variant.stock = 8
        self.variant.reserved_quantity = 0
        self.variant.save()

        # Perform cancellation
        success, message = order.cancel_order(reason="Customer cancelled too late")
        self.assertFalse(success)
        
        # Checking exact error pattern
        self.assertEqual(
            message,
            "Cancellation window closed. Order was confirmed 25 minutes ago. You can only cancel within 20 minutes of confirmation."
        )

        # Reload
        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(self.variant.stock, 8)

    def test_cancel_confirmed_order_fails_if_shop_order_processing(self):
        """
        An order cancellation should fail if any associated ShopOrder is updated to processing.
        """
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )

        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="processing",  # Vendor already processing
            subtotal=Decimal("150.00"),
            total=Decimal("150.00")
        )

        OrderItem.objects.create(
            shop_order=shop_order,
            product_variant=self.variant,
            quantity=2,
            price_at_purchase=Decimal("150.00")
        )

        self.variant.stock = 8
        self.variant.reserved_quantity = 0
        self.variant.save()

        # Perform cancellation
        success, message = order.cancel_order(reason="Customer cancel request")
        self.assertFalse(success)
        self.assertEqual(message, "Once shop begins processing, cancellation unavailable.")

        # Reload
        order.refresh_from_db()
        shop_order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(shop_order.status, "processing")


from rest_framework.test import APITestCase
from rest_framework import status

class FinancialDashboardAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_superuser(
            phone="01799999999",
            country_code="BD",
            password="AdminPassword123"
        )
        self.vendor_user = User.objects.create_user(
            phone="01788888888",
            country_code="BD",
            password="VendorPassword123",
            name="Vendor User"
        )
        self.customer = User.objects.create_user(
            phone="01777777777",
            country_code="BD",
            password="CustomerPassword123",
            name="Customer User"
        )

        # Create market and shop
        self.market = Market.objects.create(name="Feni Market", address="Feni")
        self.category = Category.objects.create(name="Electronics", slug="electronics")
        self.shop = Shop.objects.create(
            name="Feni Electronics",
            address="Feni",
            market=self.market,
            owner=self.vendor_user,
            status="approved"
        )

        # Create order & shop order
        self.order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("200.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="123 Street",
            shipping_city="Feni",
            phone_number="01777777777",
            payment_method="sslcommerz"
        )
        self.shop_order = ShopOrder.objects.create(
            order=self.order,
            shop=self.shop,
            status="delivered",
            settlement_status="unsettled",
            subtotal=Decimal("150.00"),
            total=Decimal("200.00"),
            shipping_fee=Decimal("50.00"),
            platform_commission=Decimal("15.00"),
            merchant_net=Decimal("135.00")
        )

    def test_admin_financial_dashboard_success(self):
        """Admin can access financial dashboard, and it queries correctly without FieldError."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/v1/order/admin/financials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify stats and unsettled shops
        self.assertIn("stats", response.data)
        self.assertIn("unsettled_shops", response.data)
        unsettled_shops = response.data["unsettled_shops"]
        self.assertEqual(len(unsettled_shops), 1)
        self.assertEqual(unsettled_shops[0]["shop_id"], self.shop.id)
        self.assertAlmostEqual(float(unsettled_shops[0]["net_payout"]), 35.0) # 50.00 shipping_fee - 15.00 commission

    def test_non_admin_cannot_access_admin_financial_dashboard(self):
        """Non-admin user cannot access admin financial dashboard."""
        self.client.force_authenticate(user=self.customer)
        response = self.client.get('/v1/order/admin/financials/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
