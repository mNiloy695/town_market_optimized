
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer, AddToCartSerializer
from product.models import ProductVariant
from django.shortcuts import get_object_or_404


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = serializer.variant
        quantity = serializer.validated_data['quantity']

        if variant.stock < quantity:
            return Response({'error': 'Not enough stock.'}, status=status.HTTP_400_BAD_REQUEST)
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product_variant=variant)
        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity
        cart_item.save()
        return Response(CartItemSerializer(cart_item).data, status=status.HTTP_201_CREATED)


class CartDetailView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		cart, _ = Cart.objects.get_or_create(user=request.user)
		serializer = CartSerializer(cart)
		return Response(serializer.data)
