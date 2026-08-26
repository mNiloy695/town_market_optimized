from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet
from shop.models import RequestForShop
from shop.serializers import RequestForShopSerializer


class CustomPermissionForRequestForShop(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.is_active:
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_staff
        if request.method in ['POST']:
            return not request.user.is_staff
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff


class RequestForShopView(ModelViewSet):
    queryset = RequestForShop.objects.select_related('user', 'shop').all()
    serializer_class = RequestForShopSerializer
    permission_classes = [CustomPermissionForRequestForShop]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status']
    search_fields = ['user__name', 'shop__name', 'user__phone', 'user__email', 'shop__phone']
    http_method_names = ['get', 'post', 'patch', 'put', 'delete']
