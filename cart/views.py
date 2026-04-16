
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
    

class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, variant_id):
        cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(
            CartItem,
            cart=cart,
            product_variant_id=variant_id
        )
        cart_item.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
    
    

class IncrementOrDecrementCartItemView(APIView):
    permission_classes=[IsAuthenticated]
    def patch(self,request,variant_id):
        cart=get_object_or_404(Cart,user=request.user)
        cart_item=get_object_or_404(CartItem,cart=cart,product_variant_id=variant_id)
        quantity=request.data.get('quantity', 1)
        
        if not isinstance(quantity, int) or quantity <= 0:
            return Response({'error': 'Quantity must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
        
        action=request.data.get('type')
        
        if action not in ['increment','decrement']:
            return Response({'error':'Invalid type. Must be "increment" or "decrement".'},status=status.HTTP_400_BAD_REQUEST)
        if action=='increment':
            if cart_item.product_variant.stock < cart_item.quantity + quantity:
                return Response({'error': 'Not enough stock.'}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity+=quantity
            cart_item.save()
        else:
            if cart_item.quantity-quantity<=0:
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            cart_item.quantity-=quantity
            cart_item.save()
        return Response({"message":"Cart item updated successfully.","cart_item": CartItemSerializer(cart_item).data},status=status.HTTP_200_OK)


class CartDetailView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		cart, _ = Cart.objects.get_or_create(user=request.user)
		# Prefetch related items, variants, and product info to avoid N+1 queries in serializer
		cart_qs = Cart.objects.filter(id=cart.id).prefetch_related(
			'items__product_variant__product__shop'
		)
		cart = cart_qs.first()
		serializer = CartSerializer(cart)
		return Response(serializer.data)
