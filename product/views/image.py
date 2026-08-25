from rest_framework import generics, permissions
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import BasePermission
from product.models import ProductImage
from product.serializers import ProductImageSerializer, ProductImageDeleteSerializer


class ProductImageView(generics.ListAPIView):
    queryset = ProductImage.objects.prefetch_related('product').all()
    serializer_class = ProductImageSerializer


class CustomPermissionForProductImage(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'destroy':
            return request.user and request.user.is_authenticated
        return False

    def has_object_permission(self, request, view, obj):
        if view.action == 'destroy':
            return obj.product.shop.owner == request.user
        return False


class ProductImageDeleteView(ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageDeleteSerializer
    permission_classes = [CustomPermissionForProductImage]
    http_method_names = ['delete']
