import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction, models
from django.db.models import Sum, Count, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.settings import COMMISSION_PERCENTAGE
from order.models import Order, ShopOrder, OrderTimeline
from order.serializers import (
    ShopOrderDetailSerializer, ShopOrderListSerializer,
    ShopOrderStatusUpdateSerializer, VendorOrderStatsSerializer
)
from product.models import ProductVariant

logger = logging.getLogger(__name__)


class VendorOrderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from shop.checks import get_vendor_shop
        try:
            shop = get_vendor_shop(request.user)
        except Exception as e:
            return Response(
                {'error': str(e.detail.get("detail", str(e)))},
                status=status.HTTP_403_FORBIDDEN
            )

        orders = ShopOrder.objects.filter(shop=shop).select_related('order__user')

        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)

        from rest_framework.pagination import PageNumberPagination

        class StandardPagination(PageNumberPagination):
            page_size = 20
            page_size_query_param = 'page_size'
            max_page_size = 100

        paginator = StandardPagination()
        page = paginator.paginate_queryset(orders, request)

        if page is not None:
            serializer = ShopOrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ShopOrderListSerializer(orders, many=True)
        return Response(serializer.data)


class VendorOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, shop_order_id):
        from shop.checks import get_vendor_shop
        try:
            shop = get_vendor_shop(request.user)
        except Exception as e:
            return Response(
                {'error': str(e.detail.get("detail", str(e)))},
                status=status.HTTP_403_FORBIDDEN
            )

        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, shop=shop)
        serializer = ShopOrderDetailSerializer(shop_order, context={'request': request})
        return Response(serializer.data)


class VendorOrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, shop_order_id):
        from shop.checks import get_vendor_shop
        try:
            shop = get_vendor_shop(request.user)
        except Exception as e:
            return Response(
                {'error': str(e.detail.get("detail", str(e)))},
                status=status.HTTP_403_FORBIDDEN
            )

        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, shop=shop)

        new_status = request.data.get('status', '')
        if new_status and not shop_order.order.is_paid and new_status not in ['cancelled']:
            return Response(
                {'error': 'Cannot process order: payment has not been confirmed yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ShopOrderStatusUpdateSerializer(
            shop_order, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)

        old_status = shop_order.status
        updated_order = serializer.save()

        action_map = {
            'confirmed': 'confirmed',
            'processing': 'processing',
            'shipped': 'shipped',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'return_requested': 'return_requested',
            'returned': 'returned'
        }

        OrderTimeline.objects.create(
            shop_order=updated_order,
            action=action_map.get(updated_order.status, 'status_changed'),
            description=f'Status changed from {old_status} to {updated_order.status}',
            created_by=request.user
        )

        if updated_order.status == 'confirmed':
            updated_order.confirmed_at = timezone.now()
        elif updated_order.status == 'shipped':
            updated_order.shipped_at = timezone.now()
        elif updated_order.status == 'delivered':
            updated_order.delivered_at = timezone.now()
        updated_order.save()

        return Response(
            ShopOrderDetailSerializer(updated_order, context={'request': request}).data
        )


class VendorDashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from shop.checks import get_vendor_shop
        year = request.query_params.get('year', timezone.now().year)
        month = request.query_params.get('month', None)
        day = request.query_params.get('day', None)
        try:
            shop = get_vendor_shop(request.user)
        except Exception as e:
            return Response(
                {'error': str(e.detail.get("detail", str(e)))},
                status=status.HTTP_403_FORBIDDEN
            )

        all_time_orders = ShopOrder.objects.filter(shop=shop)
        if not month and not day:
            shop_orders = all_time_orders.filter(order__created_at__year=year)
        elif month and not day:
            shop_orders = all_time_orders.filter(order__created_at__year=year, order__created_at__month=month)
        elif month and day:
            shop_orders = all_time_orders.filter(order__created_at__year=year, order__created_at__month=month, order__created_at__day=day)
        else:
            shop_orders = all_time_orders.filter(order__created_at__year=year)

        need_to_pay_commission_to_the_platform = all_time_orders.filter(status='delivered', commission_given=False).aggregate(Sum('total'))['total__sum'] or 0
        need_to_pay_commission_to_the_platform = need_to_pay_commission_to_the_platform * COMMISSION_PERCENTAGE

        stats = {
            'total_orders': shop_orders.count(),
            'pending_orders': shop_orders.filter(status='pending').count(),
            'confirmed_orders': shop_orders.filter(status='confirmed').count(),
            'shipped_orders': shop_orders.filter(status='shipped').count(),
            'total_sales': shop_orders.aggregate(Sum('total'))['total__sum'] or 0,
            'average_order_value': shop_orders.aggregate(Avg('total'))['total__avg'] or 0,
            'delivered_orders': shop_orders.filter(status='delivered').count(),
            'delivered_amount': shop_orders.filter(status='delivered').aggregate(Sum('total'))['total__sum'] or 0,
            'delivered_but_not_given_commission_amount': shop_orders.filter(status='delivered', commission_given=False).aggregate(Sum('total'))['total__sum'] or 0,
            'cancelled_orders': shop_orders.filter(status='cancelled').count(),
            'returned_orders': shop_orders.filter(status='returned').count(),
            'need_to_pay_commission_to_the_platform': need_to_pay_commission_to_the_platform or 0
        }

        serializer = VendorOrderStatsSerializer(stats)
        return Response(serializer.data)


class OrderReturnRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, shop_order_id):
        if not request.user.is_active:
            return Response(
                {'error': 'Your account has been deactivated'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            order = Order.objects.get(
                id__in=ShopOrder.objects.filter(id=shop_order_id).values('order_id'),
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        shop_order = get_object_or_404(ShopOrder, id=shop_order_id, order=order)

        if shop_order.status != 'delivered':
            return Response(
                {'error': 'Only delivered orders can be returned'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')

        try:
            with transaction.atomic():
                shop_order.status = 'return_requested'
                shop_order.save()

                OrderTimeline.objects.create(
                    shop_order=shop_order,
                    action='return_requested',
                    description=f'Return requested. Reason: {reason}',
                    created_by=request.user
                )

                return Response(
                    {
                        'message': 'Return request submitted',
                        'order': ShopOrderDetailSerializer(shop_order, context={'request': request}).data
                    },
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            logger.exception("Return request failed for user %s shop_order %s", request.user.id, shop_order_id)
            return Response(
                {'error': 'Return request failed due to an internal error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VendorReturnApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, shop_order_id):
        from shop.checks import get_vendor_shop
        try:
            shop = get_vendor_shop(request.user)
        except Exception as e:
            return Response(
                {'error': str(e.detail.get("detail", str(e)))},
                status=status.HTTP_403_FORBIDDEN
            )

        action = request.data.get('action')
        if action not in ['approve', 'reject']:
            return Response(
                {'error': 'Action must be "approve" or "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                shop_order = get_object_or_404(
                    ShopOrder.objects.select_for_update(),
                    id=shop_order_id, shop=shop
                )

                if shop_order.status != 'return_requested':
                    return Response(
                        {'error': 'Order does not have a pending return request'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if action == 'approve':
                    for item in shop_order.items.select_related('product_variant').all():
                        variant = ProductVariant.objects.select_for_update().get(id=item.product_variant_id)
                        variant.stock = models.F('stock') + item.quantity
                        variant.save(update_fields=['stock'])

                    shop_order.status = 'returned'
                    shop_order.save()

                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='returned',
                        description='Return approved - refund processed',
                        created_by=request.user
                    )

                    message = 'Return approved and stock restored'

                else:
                    reason = request.data.get('reason', 'Return request rejected')
                    shop_order.status = 'delivered'
                    shop_order.save()

                    OrderTimeline.objects.create(
                        shop_order=shop_order,
                        action='return_rejected',
                        description=f'Return rejected. Reason: {reason}',
                        created_by=request.user
                    )

                    message = 'Return request rejected'

                return Response(
                    {
                        'message': message,
                        'order': ShopOrderDetailSerializer(shop_order, context={'request': request}).data
                    },
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            logger.exception("Return approval failed for user %s shop_order %s", request.user.id, shop_order_id)
            return Response(
                {'error': 'Return approval failed due to an internal error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
