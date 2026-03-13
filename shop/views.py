from .models import Shop, RequestForShop
from .serializers import ShopSerializer, RequestForShopSerializer
from rest_framework import viewsets, permissions, serializers
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet

class ShopPagination(PageNumberPagination):
    page_size = 20

class CustomPermissionForShop(permissions.BasePermission):
    def has_permission(self,request,view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated
    
    def has_object_permission(self,request,view,obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner==request.user and obj.status=="approved" or request.user.is_superuser


    

class ShopView(ModelViewSet):
    queryset = Shop.objects.prefetch_related('Category').select_related('market','owner').all()
    serializer_class = ShopSerializer
    pagination_class = ShopPagination
    permission_classes=[CustomPermissionForShop]
    filter_backends = [DjangoFilterBackend,SearchFilter]
    filterset_fields = ['Category','is_open','status','market']
    search_fields = ['name', 'Category__name','market__name','slug']
    http_method_names = ['get','patch','put']

    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.queryset
        return self.queryset.filter(status="approved",is_deactivated=False)



class CustomPermissionForRequestForShop(permissions.BasePermission):
    def has_permission(self,request,view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated and request.user.is_staff
        if request.method in ['POST']:
            return request.user.is_authenticated and not request.user.is_staff
        if request.method in ['PATCH','PUT']:
            return request.user.is_authenticated and request.user.is_staff
        return request.user.is_authenticated and request.user.is_staff
    
    def has_object_permission(self,request,view,obj):
        return  request.user.is_superuser

class RequestForShopView(ModelViewSet):
    queryset = RequestForShop.objects.select_related('user','shop').all()
    serializer_class = RequestForShopSerializer
    permission_classes=[CustomPermissionForRequestForShop]
    filter_backends = [DjangoFilterBackend,SearchFilter]
    filterset_fields = ['status']
    search_fields = ['user__name','shop__name','user__phone','user__email','shop__phone']
    http_method_names = ['get','post']


    
    




