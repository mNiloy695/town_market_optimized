from rest_framework import generics, permissions, status
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
from shop.models import Shop
from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend 
from rest_framework.filters import SearchFilter
from django.shortcuts import get_object_or_404


class ProductPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 1000
    page_size_query_param = 'page_size'
    page_query_param = 'page'

class ParentProductCategoryListView(generics.ListAPIView):
    queryset=ParentProductCategory.objects.all()
    serializer_class=ParentProductCategorySerializer

class ProductCategoryListView(generics.ListAPIView):
    queryset=ProductCategory.objects.all()
    serializer_class=ProductCategorySerializer
    filter_backends=[DjangoFilterBackend]
    filterset_fields=['name','parent__slug']

class ProductImageView(generics.ListAPIView):
    queryset=ProductImage.objects.prefetch_related('product').all()
    serializer_class=ProductImageSerializer



class CustomProductManagePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Check if the user is the owner of the shop that own this product
        return obj.shop.owner == request.user or request.user.is_staff
from rest_framework.decorators import action
from review.serializers import ReviewSerializer
class ProductListView(ModelViewSet):
    queryset=Product.objects.select_related('shop','sub_category').prefetch_related('variants__option_values__option_value__product_category_option', 'images').all()
    serializer_class=ProductSerializer
    permission_classes = [CustomProductManagePermission]
    pagination_class = ProductPagination
    filter_backends=[DjangoFilterBackend,SearchFilter]
    filterset_fields=['shop__id']
    search_fields=['name','sub_category__slug','shop__slug','sub_category__parent__slug']

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'seller':
            shop = Shop.objects.filter(owner=user).first()

            if not shop:
                raise serializers.ValidationError({"detail": "You do not have a shop registered."})
            
            if shop.status != 'approved':
                raise serializers.ValidationError({"detail": f"Your shop is currently {shop.status}. It must be approved before you can create products."})
            
            serializer.save(shop=shop)
        else:
            raise serializers.ValidationError({"detail": "Only users with the 'seller' role can create products."})
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def product_review(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            raise serializers.ValidationError({"detail": "Product ID is required."})
        product = Product.objects.prefetch_related('reviews').filter(id=product_id).first()
        if not product:
            raise serializers.ValidationError({"detail": "Product not found."})
        reviews = product.reviews.all()
        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = ReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    

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

class ProductAvailableOptionsView(generics.GenericAPIView):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        selected_option_value_ids = request.data.get('selected_option_value_ids', [])
        selected_ids_set = set(selected_option_value_ids)
        
        variants = product.variants.filter(stock__gt=0).prefetch_related('option_values__option_value__product_category_option')
        # Filter variants that have the selected option values
        if selected_option_value_ids:
            variants = variants.filter(option_values__option_value_id__in=selected_option_value_ids)
        
        options = {}
        for variant in variants:
            for ov in variant.option_values.all():
                option_name = ov.option_value.product_category_option.name
                value = ov.option_value.value
                value_id = ov.option_value.id
                if value_id not in selected_ids_set:
                    if option_name not in options:
                        options[option_name] = {}
                    options[option_name][value] = value_id
        # Convert to list of dicts
        result = {}
        for opt_name, val_dict in options.items():
            result[opt_name] = [{"id": vid, "value": val} for val, vid in val_dict.items()]
        return Response(result)


class FindVariantView(generics.GenericAPIView):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        option_value_ids = request.data.get('option_value_ids', [])
        if not option_value_ids:
            return Response({'error': 'option_value_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        variants = product.variants.filter(stock__gt=0).prefetch_related('option_values')
        # Filter variants that have exactly these option_value_ids
        for variant in variants:
            variant_option_ids = set(variant.option_values.values_list('option_value_id', flat=True))
            if set(option_value_ids) == variant_option_ids:
                return Response({'variant_id': variant.id})
        
        return Response({'error': 'No variant found with the given option values'}, status=status.HTTP_400_BAD_REQUEST)










class MyShopProductView(generics.ListAPIView):
    queryset=Product.objects.select_related('shop','sub_category').prefetch_related('variants__option_values__option_value__product_category_option', 'images').all()
    serializer_class=ProductSerializer
    permission_classes=[permissions.IsAuthenticated]
    pagination_class = ProductPagination
    filter_backends=[SearchFilter]
    search_fields=['name','sub_category__slug','shop__slug','sub_category__parent__slug','slug']
    

    def get_queryset(self):
        user = self.request.user
        shop = Shop.objects.filter(owner=user).first()
        if not shop:
            return Product.objects.none()
        return Product.objects.filter(shop=shop)