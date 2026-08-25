from django.urls import path,include
from .views import (
    ProductCategoryListView, ParentProductCategoryListView, ProductImageView,
    ProductListView, ProductCategoryOptionListView, ProductCategoryOptionValueListView,
    ProductAvailableOptionsView, FindVariantView,MyShopProductView,ProductImageDeleteView,
    RestockView
)

from rest_framework.routers import DefaultRouter
router=DefaultRouter()
router.register('list',ProductListView)
router.register('product-image-delete',ProductImageDeleteView,basename='product-image-delete')
urlpatterns=[
    path('parent-product-category/',ParentProductCategoryListView.as_view()),
    path('product-category/',ProductCategoryListView.as_view()),
    path('product-image/',ProductImageView.as_view()),
    path('',include(router.urls)),
    path('product-category-option/',ProductCategoryOptionListView.as_view()),
    path('product-category-option-value/',ProductCategoryOptionValueListView.as_view()),
    path('<int:pk>/available-options/', ProductAvailableOptionsView.as_view(), name='product-available-options'),
    path('<int:pk>/find-variant/', FindVariantView.as_view(), name='find-variant'),
    path('vendor/my-shop-product/',MyShopProductView.as_view(), name='my-shop-product'),
    path('variant/<int:variant_id>/restock/', RestockView.as_view(), name='variant-restock'),
]