from rest_framework import generics, permissions
from django_filters.rest_framework import DjangoFilterBackend
from product.models import (
    ParentProductCategory, ProductCategory,
    ProductCategoryOption, ProductCategoryOptionValue,
)
from product.serializers import (
    ParentProductCategorySerializer, ProductCategorySerializer,
    ProductCategoryOptionSerializer, ProductCategoryOptionValueSerializer,
)


class ParentProductCategoryListView(generics.ListAPIView):
    queryset = ParentProductCategory.objects.all()
    serializer_class = ParentProductCategorySerializer


class ProductCategoryListView(generics.ListAPIView):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'parent__slug']


class ProductCategoryOptionListView(generics.ListAPIView):
    queryset = ProductCategoryOption.objects.all()
    serializer_class = ProductCategoryOptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product_category__slug', 'product_category__id']


class ProductCategoryOptionValueListView(generics.ListAPIView):
    queryset = ProductCategoryOptionValue.objects.all()
    serializer_class = ProductCategoryOptionValueSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product_category_option__slug']

    def get_queryset(self):
        queryset = super().get_queryset()
        option_slug = self.request.query_params.get('product_category_option__slug')
        if option_slug is not None and option_slug == '':
            return queryset.none()
        return queryset
