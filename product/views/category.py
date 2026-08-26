from rest_framework import generics, permissions, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from product.models import (
    ParentProductCategory, ProductCategory,
    ProductCategoryOption, ProductCategoryOptionValue,
    ProductCategoryOptionAudit,
)
from product.serializers import (
    ParentProductCategorySerializer, ProductCategorySerializer,
    ProductCategoryOptionSerializer, ProductCategoryOptionValueSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsAuthenticatedForCreateOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == "POST":
            if request.user and request.user.is_authenticated and request.user.is_staff:
                return True
            if request.user and request.user.is_authenticated:
                from shop.models import Shop
                return Shop.objects.filter(
                    owner=request.user, is_active=True, is_deactivated=False, status="approved"
                ).exists()
        return request.user and request.user.is_authenticated and request.user.is_staff


class ParentProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ParentProductCategory.objects.all()
    serializer_class = ParentProductCategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.select_related('parent').all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'parent__slug', 'parent__id']


class ProductCategoryOptionViewSet(viewsets.ModelViewSet):
    queryset = ProductCategoryOption.objects.select_related('product_category').prefetch_related('values').all()
    serializer_class = ProductCategoryOptionSerializer
    permission_classes = [IsAuthenticatedForCreateOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product_category__slug', 'product_category__id']

    def perform_create(self, serializer):
        option = serializer.save(created_by=self.request.user)
        ProductCategoryOptionAudit.objects.create(
            user=self.request.user,
            action='create_option',
            option_name=option.name
        )


class ProductCategoryOptionValueViewSet(viewsets.ModelViewSet):
    queryset = ProductCategoryOptionValue.objects.select_related('product_category_option').all()
    serializer_class = ProductCategoryOptionValueSerializer
    permission_classes = [IsAuthenticatedForCreateOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product_category_option__slug', 'product_category_option__id']

    def perform_create(self, serializer):
        val = serializer.save(created_by=self.request.user)
        ProductCategoryOptionAudit.objects.create(
            user=self.request.user,
            action='create_value',
            option_name=val.product_category_option.name,
            value_name=val.value
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        option_slug = self.request.query_params.get('product_category_option__slug')
        if option_slug is not None and option_slug == '':
            return queryset.none()
        return queryset
