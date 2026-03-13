from django.urls import path,include
from .views import (
    ProductCategoryListView, ParentProductCategoryListView, ProductImageView,
    ProductListView, ProductCategoryOptionListView, ProductCategoryOptionValueListView
)
from rest_framework.routers import DefaultRouter
router=DefaultRouter()
router.register('product',ProductListView)
urlpatterns=[
    path('parent-product-category/',ParentProductCategoryListView.as_view()),
    path('product-category/',ProductCategoryListView.as_view()),
    path('product-image/',ProductImageView.as_view()),
    path('',include(router.urls)),
    path('product-category-option/',ProductCategoryOptionListView.as_view()),
    path('product-category-option-value/',ProductCategoryOptionValueListView.as_view()),
]