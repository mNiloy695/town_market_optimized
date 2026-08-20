from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import Market, Shop, Category
from product.models import ParentProductCategory, ProductCategory, Product, ProductVariant

User = get_user_model()

class ProductVisibilityTests(APITestCase):
    def setUp(self):
        # Create standard market and category
        self.market = Market.objects.create(name="Test Market", address="Test Address")
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.parent_cat = ParentProductCategory.objects.create(name="Parent Cat")
        self.prod_cat = ProductCategory.objects.create(name="Product Cat", parent=self.parent_cat)

        # Helper to create vendor and shop
        self.vendor_counter = 0

    def create_vendor_and_shop(self, shop_name="Test Shop", shop_status="approved", shop_active=True, shop_deactivated=False, user_active=True):
        self.vendor_counter += 1
        vendor_user = User.objects.create_user(
            phone=f"0170000000{self.vendor_counter}",
            country_code="BD",
            password="testpassword123",
            name=f"Vendor {self.vendor_counter}",
            is_active=user_active
        )
        shop = Shop.objects.create(
            name=shop_name,
            address="Test Shop Address",
            market=self.market,
            owner=vendor_user,
            status=shop_status
        )
        # Apply suspension or deactivation flags after creation so signals don't overwrite them
        if not shop_active or shop_deactivated:
            shop.is_active = shop_active
            shop.is_deactivated = shop_deactivated
            shop.save()
        shop.Category.add(self.category)
        return shop

    def test_active_product_visible_when_shop_and_owner_active(self):
        """Active product from active, approved, non-deactivated shop owned by active user should be visible"""
        shop = self.create_vendor_and_shop()
        product = Product.objects.create(name="Visible Product", shop=shop, sub_category=self.prod_cat, is_active=True)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify product is in the list
        results = response.data.get('results', [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], product.id)

    def test_inactive_product_hidden(self):
        """Product with is_active=False should not be visible in public listing"""
        shop = self.create_vendor_and_shop()
        Product.objects.create(name="Inactive Product", shop=shop, sub_category=self.prod_cat, is_active=False)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)

    def test_suspended_shop_products_hidden(self):
        """Products of a suspended shop (is_active=False) should not be visible"""
        shop = self.create_vendor_and_shop(shop_active=False)
        Product.objects.create(name="Suspended Shop Product", shop=shop, sub_category=self.prod_cat, is_active=True)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)

    def test_unapproved_shop_products_hidden(self):
        """Products of a shop with status='pending' should not be visible"""
        shop = self.create_vendor_and_shop(shop_status="pending")
        Product.objects.create(name="Pending Shop Product", shop=shop, sub_category=self.prod_cat, is_active=True)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)

    def test_deactivated_shop_products_hidden(self):
        """Products of a shop with is_deactivated=True should not be visible"""
        shop = self.create_vendor_and_shop(shop_deactivated=True)
        Product.objects.create(name="Deactivated Shop Product", shop=shop, sub_category=self.prod_cat, is_active=True)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)

    def test_deactivated_owner_user_products_hidden(self):
        """Products of a shop whose owner's user account is deactivated should not be visible"""
        shop = self.create_vendor_and_shop(user_active=False)
        Product.objects.create(name="Deactivated Owner Product", shop=shop, sub_category=self.prod_cat, is_active=True)
        
        response = self.client.get('/v1/product/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)
