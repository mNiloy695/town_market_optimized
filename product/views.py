from rest_framework import generics, permissions
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

class ProductListView(ModelViewSet):
    queryset=Product.objects.select_related('shop','sub_category').all()
    serializer_class=ProductSerializer
    permission_classes = [CustomProductManagePermission]

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









