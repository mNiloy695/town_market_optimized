from django.test import TestCase
from django.test import SimpleTestCase
from django.test import RequestFactory
from unittest import mock
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal

from shop.models import Market, Shop, Category
from product.models import ParentProductCategory, ProductCategory, Product, ProductVariant
from order.models import Order, ShopOrder, OrderItem
from order.views.checkout import build_callback_url

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

    def test_cancel_order_within_1_hour_unconfirmed_succeeds(self):
        """
        An order should be cancellable within 1 hour of placing it if it is still unconfirmed by the shop owner.
        """
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )
        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="pending",  # Unconfirmed
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
        self.variant.reserved_quantity = 2
        self.variant.save()

        # Perform cancellation within 1 hour
        success, message = order.cancel_order(reason="Customer cancelled")
        self.assertTrue(success)

        # Reload
        order.refresh_from_db()
        shop_order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(shop_order.status, "cancelled")
        self.assertEqual(self.variant.stock, 10)  # Stock restored

    def test_cancel_order_after_1_hour_fails(self):
        """
        An order cannot be cancelled after 1 hour of placing it, even if shop orders are pending.
        """
        from datetime import timedelta
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )
        # Force created_at in the past
        Order.objects.filter(id=order.id).update(created_at=timezone.now() - timedelta(minutes=65))
        order.refresh_from_db()

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

        success, message = order.cancel_order(reason="Too late")
        self.assertFalse(success)
        self.assertIn("Cancellation window closed", message)

    def test_cancel_order_fails_if_shop_order_confirmed_or_processed(self):
        """
        An order cannot be cancelled if any associated ShopOrder has been confirmed by the vendor.
        """
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("150.00"),
            status="confirmed",
            is_paid=True,
            shipping_address="123 Street",
            shipping_city="feni",
            phone_number="01712345678",
            payment_method="sslcommerz"
        )
        shop_order = ShopOrder.objects.create(
            order=order,
            shop=self.shop,
            status="confirmed",  # Vendor already confirmed
            subtotal=Decimal("150.00"),
            total=Decimal("150.00")
        )
        OrderItem.objects.create(
            shop_order=shop_order,
            product_variant=self.variant,
            quantity=2,
            price_at_purchase=Decimal("150.00")
        )

        success, message = order.cancel_order(reason="Customer cancel request")
        self.assertFalse(success)
        self.assertEqual(message, "Once shop owner confirms the order, cancellation is unavailable.")


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
        # Verify stats are exposed at top level
        for key in ('total_revenue', 'total_commissions', 'total_commission_received',
                    'unsettled_merchant_liabilities', 'total_paid_out'):
            self.assertIn(key, response.data)
        # Verify ledger, settlements, commission payments and unsettled shops sections
        self.assertIn("ledger", response.data)
        self.assertIn("settlements", response.data)
        self.assertIn("commission_payments", response.data)
        unsettled_shops = response.data["unsettled_shops"]
        self.assertEqual(len(unsettled_shops), 1)
        self.assertEqual(unsettled_shops[0]["shop_id"], self.shop.id)
        self.assertAlmostEqual(float(unsettled_shops[0]["net_payout"]), 35.0)  # 50.00 shipping_fee - 15.00 commission
        # shipping_fees (50) - commission (15) means the merchant is owed, no commission liability
        self.assertEqual(float(unsettled_shops[0]["commission_liability"]), 0.0)
        self.assertEqual(float(unsettled_shops[0]["commission_paid"]), 0.0)

    def test_non_admin_cannot_access_admin_financial_dashboard(self):
        """Non-admin user cannot access admin financial dashboard."""
        self.client.force_authenticate(user=self.customer)
        response = self.client.get('/v1/order/admin/financials/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_merchant_financial_dashboard_has_commission_fields(self):
        """Merchant dashboard exposes commission liability and payments."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get('/v1/order/vendor/financials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ('total_revenue', 'paid_amount', 'unsettled_balance',
                    'commission_liability', 'commission_paid',
                    'remaining_commission_liability'):
            self.assertIn(key, response.data)
        self.assertIn("recent_ledger_entries", response.data)
        self.assertIn("commission_payments", response.data)
        # This order: shipping 50 > commission 15 -> merchant is owed, no liability
        self.assertAlmostEqual(float(response.data["commission_liability"]), 0.0)

    def test_admin_ledger_supports_filters_and_scoped_page(self):
        """Admin ledger filters (category/type/search) and ledger_page work independently of page."""
        from order.models import FinancialLedgerEntry
        for ref in ("FILT-A", "FILT-B"):
            FinancialLedgerEntry.objects.create(
                entry_type=FinancialLedgerEntry.EntryType.DEBIT,
                category=FinancialLedgerEntry.Category.COMMISSION_PAYMENT,
                amount=Decimal("10.00"),
                shop=self.shop,
                reference_id=ref,
                notes=f"Commission filter note {ref}",
            )
        FinancialLedgerEntry.objects.create(
            entry_type=FinancialLedgerEntry.EntryType.CREDIT,
            category=FinancialLedgerEntry.Category.PLATFORM_COMMISSION,
            amount=Decimal("15.00"),
            order=self.order,
            shop_order=self.shop_order,
            shop=self.shop,
            notes="Commission revenue filter note",
        )
        self.client.force_authenticate(user=self.admin_user)

        # Category filter
        resp = self.client.get('/v1/order/admin/financials/', {'ledger_category': 'commission_payment'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["ledger"]["total_count"], 2)
        self.assertTrue(all(e["category"] == "commission_payment" for e in resp.data["ledger"]["results"]))

        # Type filter
        resp = self.client.get('/v1/order/admin/financials/', {'ledger_type': 'credit'})
        self.assertEqual(resp.data["ledger"]["total_count"], 1)
        self.assertEqual(resp.data["ledger"]["results"][0]["category"], "platform_commission")

        # Search filter
        resp = self.client.get('/v1/order/admin/financials/', {'ledger_search': 'FILT-A'})
        self.assertEqual(resp.data["ledger"]["total_count"], 1)
        self.assertEqual(resp.data["ledger"]["results"][0]["reference_id"], "FILT-A")

        # Out-of-range ledger_page falls back to page 1 without disturbing other sections
        resp = self.client.get('/v1/order/admin/financials/', {'ledger_page': '999'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["ledger"]["page"], 1)
        self.assertEqual(resp.data["settlements"]["page"], 1)

    def test_merchant_ledger_filters(self):
        """Merchant ledger supports category/type/search filters scoped to their shop."""
        from order.models import FinancialLedgerEntry
        FinancialLedgerEntry.objects.create(
            entry_type=FinancialLedgerEntry.EntryType.CREDIT,
            category=FinancialLedgerEntry.Category.MERCHANT_PRODUCT_EARNING,
            amount=Decimal("135.00"),
            order=self.order,
            shop_order=self.shop_order,
            shop=self.shop,
            notes="Merchant product earning filter note",
        )
        self.client.force_authenticate(user=self.vendor_user)
        resp = self.client.get('/v1/order/vendor/financials/', {'ledger_category': 'merchant_product_earning'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["ledger"]["total_count"], 1)
        self.assertEqual(resp.data["ledger"]["results"][0]["category"], "merchant_product_earning")
        # Merchant cannot leak entries from other shops via ledger_shop
        resp = self.client.get('/v1/order/vendor/financials/', {'ledger_shop': 'Town'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_negative_payout_is_rejected_not_paid(self):
        """A settlement where commissions exceed shipping must be rejected, not paid out."""
        self.client.force_authenticate(user=self.admin_user)
        # Order where commission (150) exceeds shipping (50): merchant owes platform 100
        debt_order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("1500.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="123 Street",
            shipping_city="Feni",
            phone_number="01777777777",
            payment_method="sslcommerz"
        )
        ShopOrder.objects.create(
            order=debt_order,
            shop=self.shop,
            status="delivered",
            settlement_status="unsettled",
            subtotal=Decimal("1500.00"),
            total=Decimal("1550.00"),
            shipping_fee=Decimal("50.00"),
            platform_commission=Decimal("150.00"),
            merchant_net=Decimal("1350.00")
        )

        response = self.client.post(
            '/v1/order/admin/settlements/create/',
            {'shop_id': self.shop.id, 'transaction_reference': 'TX-REJECT-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("commission payment", response.data['error'].lower())
        # Neither order should be marked settled
        self.shop_order.refresh_from_db()
        self.assertEqual(self.shop_order.settlement_status, 'unsettled')

    def test_shop_with_no_remaining_action_is_excluded(self):
        """A shop whose commission is fully collected (no payout, no remaining due) drops out of unsettled_shops."""
        # Second shop with commission (40) > shipping (10): the merchant owes 30.
        vendor2 = User.objects.create_user(
            phone="01766666666",
            country_code="BD",
            password="VendorPassword123",
            name="Vendor Two"
        )
        shop2 = Shop.objects.create(
            name="Feni Groceries",
            address="Feni",
            market=self.market,
            owner=vendor2,
            status="approved"
        )
        debt_order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("160.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="456 St",
            shipping_city="Feni",
            phone_number="01777777777",
            payment_method="cod"
        )
        so2 = ShopOrder.objects.create(
            order=debt_order,
            shop=shop2,
            status="delivered",
            settlement_status="unsettled",
            subtotal=Decimal("150.00"),
            total=Decimal("160.00"),
            shipping_fee=Decimal("10.00"),
            platform_commission=Decimal("40.00"),
            merchant_net=Decimal("110.00")
        )
        # Fully collect the 30 commission debt.
        so2.commission_paid = Decimal("30.00")
        so2.save(update_fields=['commission_paid'])

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/v1/order/admin/financials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        shops = {s['shop_id']: s for s in response.data['unsettled_shops']}
        self.assertNotIn(shop2.id, shops)
        # The original shop (payout owed) still appears with the settle flag only.
        merchant = shops[self.shop.id]
        self.assertTrue(merchant['has_settle_due'])
        self.assertFalse(merchant['has_collect_due'])

    def test_mixed_shop_exposes_both_direction_flags(self):
        """A shop with payout-owed orders AND commission-due orders reports both flags."""
        order2 = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("160.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="789 St",
            shipping_city="Feni",
            phone_number="01777777777",
            payment_method="cod"
        )
        # Same shop, second order where commission (40) > shipping (10) -> 30 owed.
        ShopOrder.objects.create(
            order=order2,
            shop=self.shop,
            status="delivered",
            settlement_status="unsettled",
            subtotal=Decimal("150.00"),
            total=Decimal("160.00"),
            shipping_fee=Decimal("10.00"),
            platform_commission=Decimal("40.00"),
            merchant_net=Decimal("110.00")
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/v1/order/admin/financials/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        shops = {s['shop_id']: s for s in response.data['unsettled_shops']}
        merchant = shops[self.shop.id]
        # Original order: shipping 50 - commission 15 = +35 payout owed.
        self.assertTrue(merchant['has_settle_due'])
        # Added order: 40 - 10 = 30 commission due.
        self.assertTrue(merchant['has_collect_due'])


class CommissionPaymentAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            phone="01766666666",
            country_code="BD",
            password="AdminPassword123"
        )
        self.vendor_user = User.objects.create_user(
            phone="01755555555",
            country_code="BD",
            password="VendorPassword123",
            name="Vendor User"
        )
        self.customer = User.objects.create_user(
            phone="01744444444",
            country_code="BD",
            password="CustomerPassword123",
            name="Customer User"
        )

        self.market = Market.objects.create(name="Feni Market", address="Feni")
        self.category = Category.objects.create(name="Electronics", slug="electronics")
        self.shop = Shop.objects.create(
            name="Feni Electronics",
            address="Feni",
            market=self.market,
            owner=self.vendor_user,
            status="approved"
        )

        # A shop order where commission (100) > shipping (30): merchant owes platform 70.
        self.order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("1000.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="123 Street",
            shipping_city="Feni",
            phone_number="01744444444",
            payment_method="cod"
        )
        self.shop_order = ShopOrder.objects.create(
            order=self.order,
            shop=self.shop,
            status="delivered",
            settlement_status="unsettled",
            subtotal=Decimal("1000.00"),
            total=Decimal("1030.00"),
            shipping_fee=Decimal("30.00"),
            platform_commission=Decimal("100.00"),
            merchant_net=Decimal("900.00")
        )
        self.liability = Decimal("70.00")  # 100 - 30

    def test_record_commission_payment_success(self):
        """Admin records a full Merchant->Platform commission payment."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {
                'shop_id': self.shop.id,
                'amount': '70.00',
                'payment_method': 'bkash',
                'transaction_reference': 'BKASH-TX-001',
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = response.data['commission_payment']
        self.assertEqual(payment['payment_number'][:3], 'CMP')
        self.assertAlmostEqual(float(payment['liability_before']), 70.00)
        self.assertAlmostEqual(float(payment['liability_after']), 0.00)
        self.assertEqual(payment['status'], 'received')
        self.assertIn(str(self.shop_order.get_order_number()), payment['applied_order_numbers'])

        # FIFO allocation applied to the order
        self.shop_order.refresh_from_db()
        self.assertAlmostEqual(float(self.shop_order.commission_paid), 70.00)

        # Line-level allocation recorded for audit
        self.assertEqual(len(payment['allocation']), 1)
        self.assertAlmostEqual(float(payment['allocation'][0]['amount']), 70.00)
        self.assertEqual(payment['allocation'][0]['sequence'], 0)

        # Ledger entry recorded: single DEBIT, category commission_payment (shop-level)
        from order.models import FinancialLedgerEntry
        entry = FinancialLedgerEntry.objects.get(
            category=FinancialLedgerEntry.Category.COMMISSION_PAYMENT,
            entry_type=FinancialLedgerEntry.EntryType.DEBIT
        )
        self.assertAlmostEqual(float(entry.amount), 70.00)
        self.assertEqual(entry.shop_id, self.shop.id)
        self.assertIsNone(entry.shop_order_id)
        self.assertEqual(entry.reference_id, 'BKASH-TX-001')

        # settlement_status must NOT change: platform did not pay the merchant
        self.shop_order.refresh_from_db()
        self.assertEqual(self.shop_order.settlement_status, 'unsettled')

    def test_commission_payments_apply_fifo(self):
        """Partial payments offset the oldest unsettled orders first."""
        self.client.force_authenticate(user=self.admin_user)
        from datetime import timedelta
        # Force the setup order to be the OLDEST delivered order.
        ShopOrder.objects.filter(id=self.shop_order.id).update(
            delivered_at=timezone.now() - timedelta(hours=5)
        )
        # Second, newer delivered order with debt 20 (commission 40 - shipping 20)
        newer_order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("400.00"),
            status="delivered",
            is_paid=True,
            confirmed_at=timezone.now(),
            shipping_address="456 Street",
            shipping_city="Feni",
            phone_number="01744444444",
            payment_method="cod"
        )
        newer_shop_order = ShopOrder.objects.create(
            order=newer_order,
            shop=self.shop,
            status="delivered",
            settlement_status="unsettled",
            delivered_at=timezone.now(),
            subtotal=Decimal("400.00"),
            total=Decimal("420.00"),
            shipping_fee=Decimal("20.00"),
            platform_commission=Decimal("40.00"),
            merchant_net=Decimal("360.00")
        )
        # Oldest order debt: 70 (100 - 30). Newest debt: 20. Total liability: 90.
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '80.00',
             'transaction_reference': 'FIFO-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = response.data['commission_payment']
        self.assertAlmostEqual(float(payment['liability_before']), 90.00)
        self.assertAlmostEqual(float(payment['liability_after']), 10.00)

        # Oldest order fully paid (70), newest partial (10 of 20)
        self.shop_order.refresh_from_db()
        newer_shop_order.refresh_from_db()
        self.assertAlmostEqual(float(self.shop_order.commission_paid), 70.00)
        self.assertAlmostEqual(float(newer_shop_order.commission_paid), 10.00)

        # Only orders that received an allocation are recorded on the payment
        self.assertEqual(response.data['commission_payment']['orders_count'], 2)

        # FIFO line-level allocation with per-order amounts and sequence
        alloc = response.data['commission_payment']['allocation']
        self.assertEqual(len(alloc), 2)
        self.assertAlmostEqual(float(alloc[0]['amount']), 70.00)
        self.assertEqual(alloc[0]['sequence'], 0)
        self.assertAlmostEqual(float(alloc[1]['amount']), 10.00)
        self.assertEqual(alloc[1]['sequence'], 1)

        # Structural integrity: lines sum to the payment amount
        from order.models import CommissionPaymentLine
        lines = CommissionPaymentLine.objects.filter(payment__transaction_reference='FIFO-1')
        self.assertEqual(lines.count(), 2)
        self.assertAlmostEqual(
            sum(line.amount for line in lines), 80.00
        )

    def test_partial_commission_payment(self):
        """Partial payment keeps remaining liability intact."""
        self.client.force_authenticate(user=self.admin_user)
        r1 = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '40.00',
             'transaction_reference': 'PARTIAL-1'},
            format='json'
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.data)
        self.assertAlmostEqual(float(r1.data['commission_payment']['liability_after']), 30.00)

        r2 = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '30.00',
             'transaction_reference': 'PARTIAL-2'},
            format='json'
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)
        self.assertAlmostEqual(float(r2.data['commission_payment']['liability_after']), 0.00)

    def test_overpayment_rejected_without_credit_flag(self):
        """Paying more than the liability is rejected unless overpay_credit=true."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '120.00',
             'transaction_reference': 'OVERPAY-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds', response.data['error'])

    def test_overpayment_with_credit_flag_records_merchant_credit(self):
        """With overpay_credit=true the excess is recorded as advance credit."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '120.00',
             'transaction_reference': 'OVERPAY-2', 'overpay_credit': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = response.data['commission_payment']
        self.assertTrue(payment['overpay_credit'])
        self.assertAlmostEqual(float(payment['liability_after']), 0.00)

    def test_duplicate_transaction_reference_rejected(self):
        """Same reference twice must not create two payments (idempotency)."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'shop_id': self.shop.id,
            'amount': '70.00',
            'transaction_reference': 'DUPLICATE-1',
        }
        r1 = self.client.post('/v1/order/admin/commission-payments/', payload, format='json')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post('/v1/order/admin/commission-payments/', payload, format='json')
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)

    def test_commission_payment_requires_reference(self):
        """transaction_reference is mandatory for idempotency."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '70.00'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_record_commission_payment(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '70.00',
             'transaction_reference': 'NOPE-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_commission_payment_history_get(self):
        """GET exposes the full transaction history with filters."""
        self.client.force_authenticate(user=self.admin_user)
        self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '70.00',
             'transaction_reference': 'HIST-1'},
            format='json'
        )
        response = self.client.get('/v1/order/admin/commission-payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        self.assertIn('HIST-1', response.data['results'][0]['transaction_reference'])

        # Filter by shop name
        filtered = self.client.get(
            '/v1/order/admin/commission-payments/', {'shop': 'Feni'}
        )
        self.assertEqual(filtered.data['total_count'], 1)
        no_match = self.client.get(
            '/v1/order/admin/commission-payments/', {'shop': 'Nowhere'}
        )
        self.assertEqual(no_match.data['total_count'], 0)

    def test_overpayment_records_merchant_credit(self):
        """Overpay credit is stored on the payment for the audit trail."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/v1/order/admin/commission-payments/',
            {'shop_id': self.shop.id, 'amount': '120.00',
             'transaction_reference': 'OVERPAY-3', 'overpay_credit': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = response.data['commission_payment']
        self.assertTrue(payment['overpay_credit'])
        self.assertAlmostEqual(float(payment['overpaid_amount']), 50.00)
        self.assertAlmostEqual(float(payment['liability_after']), 0.00)
        self.shop_order.refresh_from_db()
        self.assertAlmostEqual(float(self.shop_order.commission_paid), 70.00)


class CallbackUrlTests(SimpleTestCase):
    """PAYMENT_CALLBACK_BASE_URL must override the request host for gateway callbacks,
    so SSLCommerz redirects the buyer to a reachable URL instead of the internal
    Docker hostname (townmarket-web-dev:8000)."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_base_url_wins_over_request_host(self):
        request = self.factory.get('/v1/order/checkout/')
        request.META['HTTP_HOST'] = 'townmarket-web-dev:8000'
        with mock.patch('order.views.checkout.PAYMENT_CALLBACK_BASE_URL', 'http://localhost:8000'):
            self.assertEqual(
                build_callback_url(request, '/v1/order/webhook/sslcommerz/'),
                'http://localhost:8000/v1/order/webhook/sslcommerz/'
            )

    def test_falls_back_to_request_host_when_unset(self):
        request = self.factory.get('/v1/order/checkout/', SERVER_NAME='testserver')
        with mock.patch('order.views.checkout.PAYMENT_CALLBACK_BASE_URL', ''):
            self.assertEqual(
                build_callback_url(request, '/v1/order/webhook/sslcommerz/'),
                'http://testserver/v1/order/webhook/sslcommerz/'
            )
