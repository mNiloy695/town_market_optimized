from django.urls import path
from .views import (
    ProductCategoryListView, ParentProductCategoryListView, ProductImageView,
    ProductListView, ProductCategoryOptionListView, ProductCategoryOptionValueListView
)

urlpatterns=[
    path('parent-product-category/',ParentProductCategoryListView.as_view()),
    path('product-category/',ProductCategoryListView.as_view()),
    path('product-image/',ProductImageView.as_view()),
    path('product/',ProductListView.as_view()),
    path('product-category-option/',ProductCategoryOptionListView.as_view()),
    path('product-category-option-value/',ProductCategoryOptionValueListView.as_view()),
]