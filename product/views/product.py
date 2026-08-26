from rest_framework import generics, permissions, serializers, status
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import F
from django.shortcuts import get_object_or_404

from product.models import Product, ProductImage
from product.serializers import (
    ProductSerializer, ProductImageSerializer, ProductImageDeleteSerializer
)
from shop.models import Shop
from review.serializers import ReviewSerializer


class ProductPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 1000
    page_size_query_param = 'page_size'
    page_query_param = 'page'


class CustomProductManagePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
        if not request.user.is_active:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        shop = obj.shop
        return (
            shop.owner == request.user
            and request.user.is_active
            and shop.is_active
            and not shop.is_deactivated
            and shop.status == 'approved'
        )


class ProductListView(ModelViewSet):
    queryset = Product.objects.none()
    serializer_class = ProductSerializer
    permission_classes = [CustomProductManagePermission]
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['shop__id']
    search_fields = ['name', 'sub_category__slug', 'shop__slug', 'sub_category__parent__slug']

    def get_queryset(self):
        queryset = Product.objects.select_related('shop', 'sub_category').prefetch_related(
            'variants__option_values__option_value__product_category_option',
            'images',
            'reviews',
        ).order_by('-created_at').all()
        if self.request.method in permissions.SAFE_METHODS:
            queryset = queryset.filter(
                is_active=True,
                shop__owner__is_active=True,
                shop__is_active=True,
                shop__status='approved',
                shop__is_deactivated=False
            )
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'seller':
            raise serializers.ValidationError({"detail": "Only users with the 'seller' role can create products."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "Your account has been deactivated."})

        shop = Shop.objects.filter(owner=user).first()

        if not shop:
            raise serializers.ValidationError({"detail": "You do not have a shop registered."})

        if shop.status != 'approved':
            raise serializers.ValidationError({"detail": f"Your shop is currently {shop.status}. It must be approved before you can create products."})

        if not shop.is_active:
            raise serializers.ValidationError({"detail": "Your shop has been deactivated. Please contact support."})

        if shop.is_deactivated:
            raise serializers.ValidationError({"detail": "Your shop has been deactivated. Please contact support."})

        serializer.save(shop=shop)

    from rest_framework.decorators import action

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


class MyShopProductView(generics.ListAPIView):
    queryset = Product.objects.select_related('shop', 'sub_category').prefetch_related('variants__option_values__option_value__product_category_option', 'images').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'sub_category__slug', 'shop__slug', 'sub_category__parent__slug', 'slug']

    def get_queryset(self):
        from shop.checks import get_vendor_shop
        try:
            shop = get_vendor_shop(self.request.user)
        except Exception:
            return Product.objects.none()
        return Product.objects.filter(shop=shop)
