import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from order.models import Order
from order.serializers import OrderDetailSerializer, OrderListSerializer

logger = logging.getLogger(__name__)


class OrderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from rest_framework.pagination import PageNumberPagination

        class StandardPagination(PageNumberPagination):
            page_size = 20
            page_size_query_param = 'page_size'
            max_page_size = 100

        orders = Order.objects.filter(user=request.user).prefetch_related('shop_orders')

        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(orders, request)

        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        serializer = OrderDetailSerializer(order, context={'request': request})
        return Response(serializer.data)


class CustomerOrderCancel(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        success, message = order.cancel_order(reason='Order cancelled by customer')

        if success:
            return Response(
                {'message': message},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )


class PayNowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status != 'pending_payment' or order.is_paid:
            return Response(
                {'error': f'Order is already {order.status} or paid.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .checkout import CheckoutView
        checkout_view = CheckoutView()

        if order.payment_method == 'bkash':
            payment_response = checkout_view._initiate_bkash_payment(request, order)
        else:
            payment_response = checkout_view._initiate_sslcommerz_payment(request, order)

        if payment_response.get('status') == 'SUCCESS':
            return Response({
                'payment_url': payment_response.get('GatewayPageURL') or payment_response.get('checkout_url')
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': payment_response.get('failedreason') or payment_response.get('error', 'Could not initiate payment')
            }, status=status.HTTP_400_BAD_REQUEST)


class PaymentConfirmationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.status != 'pending_payment':
            return Response(
                {'error': f'Order is already {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.is_paid:
            return Response(
                {'error': 'Payment already confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.db import transaction
            with transaction.atomic():
                order.confirm_payment()

                return Response(
                    {
                        'message': 'Payment confirmed successfully',
                        'order': OrderDetailSerializer(order, context={'request': request}).data,
                        'next_step': 'Vendors are processing your order',
                        'status': 'confirmed'
                    },
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            logger.exception("Payment confirmation failed for user %s order %s", request.user.id, order_id)
            return Response(
                {'error': 'Payment confirmation failed due to an internal error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
