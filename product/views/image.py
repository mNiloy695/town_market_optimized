from rest_framework import generics, permissions
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import BasePermission
from product.models import ProductImage
from product.serializers import ProductImageSerializer, ProductImageDeleteSerializer


class ProductImageView(generics.ListAPIView):
    serializer_class = ProductImageSerializer

    def get_queryset(self):
        return ProductImage.objects.prefetch_related('product').filter(
            product__is_active=True,
            product__shop__is_active=True,
            product__shop__is_deactivated=False,
            product__shop__status='approved',
        )


class CustomPermissionForProductImage(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'destroy':
            return request.user and request.user.is_authenticated and request.user.is_active
        return False

    def has_object_permission(self, request, view, obj):
        if view.action == 'destroy':
            shop = obj.product.shop
            return (
                shop.owner == request.user
                and request.user.is_active
                and shop.is_active
                and not shop.is_deactivated
                and shop.status == 'approved'
            )
        return False


class ProductImageDeleteView(ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageDeleteSerializer
    permission_classes = [CustomPermissionForProductImage]
    http_method_names = ['delete']
