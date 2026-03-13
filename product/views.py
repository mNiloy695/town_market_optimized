from rest_framework import generics
from .models import (
    Product, ProductCategory, ProductImage, ParentProductCategory, 
    ProductCategoryOption, ProductCategoryOptionValue
)
from .serializers import (
    ProductSerializer, ProductCategorySerializer, ProductImageSerializer,
    ParentProductCategorySerializer, ProductCategoryOptionSerializer,
    ProductCategoryOptionValueSerializer
)
from django_filters.rest_framework import DjangoFilterBackend

class ParentProductCategoryListView(generics.ListAPIView):
    queryset=ParentProductCategory.objects.all()
    serializer_class=ParentProductCategorySerializer

class ProductCategoryListView(generics.ListAPIView):
    queryset=ProductCategory.objects.all()
    serializer_class=ProductCategorySerializer
    filter_backends=[DjangoFilterBackend]
    filterset_fields=['name','parent__slug']

class ProductImageView(generics.ListAPIView):
    queryset=ProductImage.objects.all()
    serializer_class=ProductImageSerializer

class ProductListView(generics.ListCreateAPIView):
    queryset=Product.objects.all()
    serializer_class=ProductSerializer

class ProductCategoryOptionListView(generics.ListAPIView):
    queryset=ProductCategoryOption.objects.all()
    serializer_class=ProductCategoryOptionSerializer
    filter_backends=[DjangoFilterBackend]
    filterset_fields=['product_category__slug', 'product_category__id']

class ProductCategoryOptionValueListView(generics.ListAPIView):
    queryset=ProductCategoryOptionValue.objects.all()
    serializer_class=ProductCategoryOptionValueSerializer
    filter_backends=[DjangoFilterBackend]
    filterset_fields=['product_category_option__slug']

    def get_queryset(self):
        queryset = super().get_queryset()
        option_slug = self.request.query_params.get('product_category_option__slug')
        
        # If the parameter is present but empty, return an empty queryset
        if option_slug is not None and option_slug == '':
            return queryset.none()
            
        return queryset






#option value varianet with product









