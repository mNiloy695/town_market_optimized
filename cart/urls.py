from django.urls import path
from .views import AddToCartView, CartDetailView,RemoveFromCartView,IncrementOrDecrementCartItemView

urlpatterns = [
	path('add/', AddToCartView.as_view(), name='cart-add'),
	path('detail/', CartDetailView.as_view(), name='cart-detail'),
    path('remove/item/<int:variant_id>/',RemoveFromCartView.as_view(),name='cart-remove'),
    path('increment-decrement/item/<int:variant_id>/',IncrementOrDecrementCartItemView.as_view(),name='cart-increment-decrement'),
]

