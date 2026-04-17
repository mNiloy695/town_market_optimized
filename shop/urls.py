from django.urls import path,include
from .views import ShopView,RequestForShopView,MarketView
from rest_framework.routers import DefaultRouter
router=DefaultRouter()
router.register('list',ShopView,basename='shop')
router.register('request',RequestForShopView,basename='request')
router.register('market',MarketView,basename='market')
urlpatterns=[
    path('',include(router.urls)),

]