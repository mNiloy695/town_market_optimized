from django.urls import path, include
from .views import (
    ProductCategoryViewSet, ParentProductCategoryViewSet, ProductImageView,
    ProductListView, ProductCategoryOptionViewSet, ProductCategoryOptionValueViewSet,
    ProductAvailableOptionsView, FindVariantView, MyShopProductView, ProductImageDeleteView,
    RestockView
)

from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('list', ProductListView)
router.register('product-image-delete', ProductImageDeleteView, basename='product-image-delete')
router.register('parent-product-category', ParentProductCategoryViewSet, basename='parent-product-category')
router.register('product-category', ProductCategoryViewSet, basename='product-category')
router.register('product-category-option', ProductCategoryOptionViewSet, basename='product-category-option')
router.register('product-category-option-value', ProductCategoryOptionValueViewSet, basename='product-category-option-value')

urlpatterns = [
    path('product-image/', ProductImageView.as_view()),
    path('', include(router.urls)),
    path('<int:pk>/available-options/', ProductAvailableOptionsView.as_view(), name='product-available-options'),
    path('<int:pk>/find-variant/', FindVariantView.as_view(), name='find-variant'),
    path('vendor/my-shop-product/', MyShopProductView.as_view(), name='my-shop-product'),
    path('variant/<int:variant_id>/restock/', RestockView.as_view(), name='variant-restock'),
]
