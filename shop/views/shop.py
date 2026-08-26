from rest_framework import viewsets, permissions, serializers
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from django.db import models
from shop.models import Shop, Category, Market
from shop.serializers import ShopSerializer, CategorySerializer, MarketSerializer


class ShopPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 1000
    page_size_query_param = 'page_size'
    page_query_param = 'page'


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff


class CustomPermissionForShop(permissions.BasePermission):
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
        return (
            obj.owner == request.user
            and obj.status == "approved"
            and obj.is_active
            and not obj.is_deactivated
        )


class ShopView(ModelViewSet):
    queryset = Shop.objects.prefetch_related('Category').select_related('market', 'owner').all()
    serializer_class = ShopSerializer
    pagination_class = ShopPagination
    permission_classes = [CustomPermissionForShop]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['Category', 'is_open', 'status', 'market']
    search_fields = ['name', 'Category__name', 'market__name', 'slug']
    http_method_names = ['get', 'patch', 'put']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        q = models.Q(status="approved", is_deactivated=False, is_active=True)
        if self.request.user.is_authenticated:
            q |= models.Q(owner=self.request.user)
        return self.queryset.filter(q)


class CategoryView(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class MarketView(ModelViewSet):
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'put', 'delete']
