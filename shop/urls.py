from django.urls import path,include
from .views import ShopView,RequestForShopView
from rest_framework.routers import DefaultRouter
router=DefaultRouter()
router.register('list',ShopView,basename='shop')
router.register('request',RequestForShopView,basename='request')
urlpatterns=[
    path('',include(router.urls)),

]