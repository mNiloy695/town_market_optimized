import logging
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction, models
from django.shortcuts import get_object_or_404

from order.models import Order, ShopOrder, OrderItem
from order.serializers import (
    CheckoutSerializer, OrderDetailSerializer,
    ShopOrderDetailSerializer
)
from cart.models import Cart
from core.settings import SHIPPING_FEE, PAYMENT_CALLBACK_BASE_URL
from product.models import ProductVariant

logger = logging.getLogger(__name__)


def build_callback_url(request, path):
    """Build a public callback URL for a payment gateway.

    Prefers the configured PAYMENT_CALLBACK_BASE_URL (reachable from the
    buyer's browser) and falls back to the request's own scheme+host.
    """
    if PAYMENT_CALLBACK_BASE_URL:
        return PAYMENT_CALLBACK_BASE_URL + path
    return request.build_absolute_uri(path)


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response(
                {'error': 'Your account has been deactivated'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                for old_order in Order.objects.filter(user=request.user, status='pending_payment'):
                    old_order.fail_order(reason='New checkout initiated, previous pending order cancelled.')

                cart = get_object_or_404(Cart, user=request.user)
                if not cart.items.exists():
                    return Response(
                        {'error': 'Cart is empty'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                for cart_item in cart.items.select_related('product_variant__product__shop__owner').all():
                    variant = cart_item.product_variant
                    locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)

                    product = locked_variant.product
                    shop = product.shop
                    if not product.is_active or not shop.is_active or shop.is_deactivated or shop.status != 'approved' or not shop.owner.is_active:
                        return Response(
                            {'error': 'One or more items in your cart are no longer available.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if locked_variant.available_stock < cart_item.quantity:
                        return Response(
                            {
                                'error': f"Not enough stock for {locked_variant.product.name}. Only {locked_variant.available_stock} is available",
                                'available': locked_variant.available_stock,
                                'requested': cart_item.quantity
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                shop_items = self._group_items_by_shop(cart)

                grand_total = sum(
                    sum(item.product_variant.price * item.quantity
                        for item in items)
                    for items in shop_items.values()
                )

                order = Order.objects.create(
                    user=request.user,
                    total_amount=grand_total,
                    status='pending_payment',
                    shipping_address=serializer.validated_data['shipping_address'],
                    shipping_city=serializer.validated_data['shipping_city'],
                    shipping_upazilla=serializer.validated_data['shipping_upazilla'],
                    shipping_postal_code=serializer.validated_data['shipping_postal_code'],
                    shipping_country=serializer.validated_data['shipping_country'],
                    phone_number=serializer.validated_data['phone_number'],
                    payment_method=serializer.validated_data['payment_method']
                )

                shop_orders = []
                for shop, cart_items in shop_items.items():
                    shop_order = self._create_shop_order(order, shop, cart_items)
                    shop_orders.append(shop_order)

                total_shipping_fee = sum(so.shipping_fee for so in shop_orders)
                total_order_amount = sum(so.total for so in shop_orders)

                order.total_amount = total_order_amount
                order.shipping_fee = total_shipping_fee
                order.cod_amount = total_order_amount - total_shipping_fee
                order.save(update_fields=['total_amount', 'shipping_fee', 'cod_amount'])

                # Sync the Invoice amount with the updated total_amount
                from invoice.models import Invoice
                Invoice.objects.filter(order=order).update(amount=total_order_amount)

                payment_method = serializer.validated_data['payment_method']

                if payment_method == 'bkash':
                    payment_response = self._initiate_bkash_payment(request, order)
                else:
                    payment_response = self._initiate_sslcommerz_payment(request, order)

                if payment_response.get('status') == 'SUCCESS':
                    return Response(
                        {
                            'message': 'Order created successfully',
                            'payment_url': payment_response.get('GatewayPageURL') or payment_response.get('checkout_url'),
                            'order': OrderDetailSerializer(order, context={'request': request}).data
                        },
                        status=status.HTTP_201_CREATED
                    )
                else:
                    return Response(
                        {
                            'message': 'Order created but payment initiation failed',
                            'error': payment_response.get('failedreason') or payment_response.get('error'),
                            'order': OrderDetailSerializer(order, context={'request': request}).data
                        },
                        status=status.HTTP_201_CREATED
                    )

        except Exception as e:
            logger.exception("Checkout failed for user %s", request.user.id)
            return Response(
                {'error': 'Checkout failed due to an internal error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _initiate_sslcommerz_payment(self, request, order):
        from order.services.sslcommerz_service import SslCommerzService
        from django.urls import reverse

        sslcz = SslCommerzService()

        webhook_url = build_callback_url(request, reverse('order:sslcommerz-webhook'))

        cus_name = request.user.phone or "Customer"
        if hasattr(request.user, 'get_full_name') and request.user.get_full_name():
            cus_name = request.user.get_full_name()
        cus_name = ''.join(e for e in cus_name if e.isalnum() or e.isspace())[:30]

        customer_email = getattr(request.user, 'email', 'customer@example.com')
        customer_phone = order.phone_number[:15]

        return sslcz.create_payment(order, webhook_url, cus_name, customer_email, customer_phone)

    def _initiate_bkash_payment(self, request, order):
        from order.services.bkash_service import BkashService
        from django.urls import reverse

        bkash = BkashService()
        base_url = f"{request.scheme}://{request.get_host()}"
        success_url = base_url + reverse('order:bkash-success', kwargs={'payment_id': 'PLACEHOLDER'})
        fail_url = base_url + reverse('order:bkash-fail', kwargs={'payment_id': 'PLACEHOLDER'})
        cancel_url = base_url + reverse('order:bkash-cancel', kwargs={'payment_id': 'PLACEHOLDER'})

        payer_ref = order.phone_number or str(request.user.id)
        amount = order.shipping_fee

        result = bkash.create_payment(
            payer_reference=payer_ref,
            amount=amount,
            merchant_invoice_number=order.order_number,
        )

        if result.get('success'):
            payment_id = result['payment_id']
            from invoice.models import Invoice
            Invoice.objects.filter(order=order).update(val_id=payment_id)
            # Replace PLACEHOLDER with actual payment_id in callback URLs
            success_url = success_url.replace('PLACEHOLDER', payment_id)
            fail_url = fail_url.replace('PLACEHOLDER', payment_id)
            cancel_url = cancel_url.replace('PLACEHOLDER', payment_id)

            checkout_url = result['checkout_url']
            # bKash checkout URL accepts callback params as query string
            separator = '&' if '?' in checkout_url else '?'
            checkout_url += f"{separator}success={success_url}&fail={fail_url}&cancel={cancel_url}"

            return {
                'status': 'SUCCESS',
                'checkout_url': checkout_url,
            }
        else:
            return {'status': 'FAILED', 'error': result.get('error', 'bKash payment creation failed')}

    def _group_items_by_shop(self, cart):
        shop_items = {}
        for cart_item in cart.items.select_related('product_variant__product__shop').all():
            shop = cart_item.product_variant.product.shop
            if shop not in shop_items:
                shop_items[shop] = []
            shop_items[shop].append(cart_item)
        return shop_items

    def _create_shop_order(self, order, shop, cart_items):
        subtotal = sum(
            item.product_variant.price * item.quantity
            for item in cart_items
        )
        shipping_fee = max(getattr(item.product_variant.product, 'shipping_fee', 50.00) or 50.00 for item in cart_items)
        tax = 0
        discount = 0

        total = subtotal + tax + shipping_fee - discount

        from decimal import Decimal
        from django.conf import settings
        comm_pct = getattr(settings, 'COMMISSION_PERCENTAGE', Decimal('0.10'))

        shop_order = ShopOrder.objects.create(
            order=order,
            shop=shop,
            subtotal=subtotal,
            tax=tax,
            shipping_fee=shipping_fee,
            discount=discount,
            total=total,
            status='pending',
            commission_percentage=comm_pct
        )

        for cart_item in cart_items:
            OrderItem.objects.create(
                shop_order=shop_order,
                product_variant=cart_item.product_variant,
                quantity=cart_item.quantity,
                price_at_purchase=cart_item.product_variant.price
            )

            variant = cart_item.product_variant
            variant.reserved_quantity = models.F('reserved_quantity') + cart_item.quantity
            variant.save(update_fields=['reserved_quantity'])

        return shop_order
