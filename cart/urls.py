from django.urls import path
from .views import AddToCartView, CartDetailView

urlpatterns = [
	path('add/', AddToCartView.as_view(), name='cart-add'),
	path('detail/', CartDetailView.as_view(), name='cart-detail'),
]
