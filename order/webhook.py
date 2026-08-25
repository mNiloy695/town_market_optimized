import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status  
from .models import Order, MoneyDectedButOrderFailed
from .serializers import OrderDetailSerializer as OrderSerializer
import requests
from rest_framework.permissions import AllowAny
from invoice.models import Invoice
from django.conf import settings
from django.db import transaction
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class IpnViewWebhookSSLCommerze(APIView):
    # NEW-01: Explicit public access — SSLCommerz does not send JWT tokens.
    # Setting authentication_classes = [] prevents DRF from rejecting
    # legitimate callbacks that lack an Authorization header.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        val_id = data.get('val_id')
        tran_id = data.get('tran_id')
        currency = data.get('currency')
        payment_status = data.get('status') 
        logger.info("Received IPN for tran_id=%s status=%s", tran_id, payment_status)

        # ── NEW-07: Call SSLCommerz validation API BEFORE acquiring DB lock. ──
        # Network I/O should never happen while holding a select_for_update row lock.
        if not val_id:
            logger.warning(
                "IPN received without val_id (status=%s). Ignoring unverifiable callback.",
                payment_status,
            )
            return Response(
                {'error': 'Missing val_id – cannot verify payment status'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        from order.services.sslcommerz_service import SslCommerzService
        sslcz = SslCommerzService()
        validation = sslcz.validate_payment(val_id)

        if not validation:
            logger.error("SSLCommerz validation API unreachable for val_id=%s", val_id)
            return Response(
                {'error': 'Payment gateway verification unavailable. No action taken.'},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # ── NEW-03: Now enter the transaction with row lock ──
        try:
            with transaction.atomic():
                order = (
                    Order.objects
                    .select_for_update()
                    .filter(order_number=tran_id)
                    .first()
                )

                if not order:
                    logger.warning("Order not found for transaction ID: %s", tran_id)
                    return Response(
                        {'error': 'Order not found'},
                        status=http_status.HTTP_404_NOT_FOUND
                    )

                if order.is_paid:
                    return Response(
                        {'message': 'Already paid, skipping'},
                        status=http_status.HTTP_200_OK
                    )

                try:
                    invoice = Invoice.objects.select_for_update().get(order=order)
                except Invoice.DoesNotExist:
                    invoice = None

                # ── NEW-04: Only mark IPN verified AFTER successful gateway contact ──
                if invoice:
                    invoice.is_ipn_verified = True
                    invoice.save(update_fields=['is_ipn_verified'])

                # ── NEW-02: Cross-verify tran_id from validation response ──
                # Ensures the val_id actually belongs to THIS order and not
                # a different transaction the attacker controls.
                validated_tran_id = validation.get('tran_id', '')
                if validated_tran_id and validated_tran_id != order.order_number:
                    logger.warning(
                        "tran_id mismatch: order has %s but validation returned %s. "
                        "Possible cross-order injection attempt.",
                        order.order_number, validated_tran_id,
                    )
                    return Response(
                        {'error': 'Transaction ID mismatch – validation rejected'},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

                # Use the gateway-verified status, NOT the raw POST status.
                verified_status = validation.get('status', '')

                if verified_status == 'VALID':
                    return self._handle_valid(order, invoice, validation, data, val_id, currency)

                elif verified_status in ['FAILED', 'CANCELLED', 'UNATTEMPTED', 'EXPIRED']:
                    return self._handle_failure(order, invoice, verified_status, val_id)

                elif verified_status == 'VALIDATED':
                    # VALIDATED means already validated — treat as idempotent VALID.
                    # NEW-A1: Must check order status to prevent resurrecting failed/cancelled orders.
                    if order.status in ['failed', 'cancelled']:
                        # Route to recovery path, same as VALID on a closed order.
                        recovery = self._track_money_deducted_for_failed_order(
                            order=order,
                            validation=validation,
                            request_data=data,
                        )
                        if invoice:
                            invoice.status = 'MONEY_DEDUCTED_ORDER_FAILED'
                            invoice.gateway_status = 'VALID'
                            invoice.is_paid = False
                            invoice.val_id = val_id
                            invoice.bank_tran_id = validation.get('bank_tran_id', '') or data.get('bank_tran_id', '')
                            invoice.card_type = validation.get('card_type', '') or data.get('card_type', '')
                            invoice.amount = self._to_decimal(validation.get('amount', 0))
                            invoice.currency = validation.get('currency', '') or currency
                            invoice.save()
                        return Response(
                            {
                                'message': 'Payment succeeded after order closed. Logged for manual reconciliation.',
                                'order_status': order.status,
                                'recovery_id': recovery.id
                            },
                            status=http_status.HTTP_200_OK
                        )
                    if not order.is_paid:
                        order.confirm_payment()
                    serializer = OrderSerializer(order)
                    return Response(serializer.data, status=http_status.HTTP_200_OK)

                else:
                    logger.warning(
                        "Unknown verified_status '%s' from gateway for order %s",
                        verified_status, order.order_number,
                    )
                    return Response(
                        {'error': f'Unknown gateway status: {verified_status}'},
                        status=http_status.HTTP_400_BAD_REQUEST
                    )

        except Exception as e:
            logger.exception("Unexpected error processing IPN for tran_id=%s: %s", tran_id, e)
            return Response(
                {'error': 'Internal processing error'},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_valid(self, order, invoice, validation, data, val_id, currency):
        """Handle gateway-verified VALID status."""
        real_amount = self._to_decimal(validation.get('amount', 0))
        real_currency = validation.get('currency', '')
        expected_amount = order.total_amount
        expected_currency = 'BDT'

        if real_amount != expected_amount or real_currency != expected_currency:
            logger.warning(
                "Amount/currency mismatch for order %s: expected %s %s, got %s %s",
                order.order_number, expected_amount, expected_currency,
                real_amount, real_currency,
            )
            if order.status not in ['failed', 'cancelled', 'confirmed']:
                order.fail_order(reason='Payment amount/currency mismatch')
            if invoice:
                invoice.status = 'FAILED'
                invoice.gateway_status = 'FAILED'
                invoice.is_paid = False
                invoice.val_id = val_id
                invoice.save()
            return Response(
                {'error': 'Amount or currency mismatch!'},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Recovery tracking for late successful payment on a closed order.
        if order.status in ['failed', 'cancelled']:
            recovery = self._track_money_deducted_for_failed_order(
                order=order,
                validation=validation,
                request_data=data,
            )
            if invoice:
                invoice.status = 'MONEY_DEDUCTED_ORDER_FAILED'
                invoice.gateway_status = 'VALID'
                invoice.is_paid = False
                invoice.val_id = val_id
                invoice.bank_tran_id = validation.get('bank_tran_id', '') or data.get('bank_tran_id', '')
                invoice.card_type = validation.get('card_type', '') or data.get('card_type', '')
                invoice.amount = self._to_decimal(validation.get('amount', 0))
                invoice.currency = validation.get('currency', '') or currency
                invoice.save()
            return Response(
                {
                    'message': 'Payment succeeded after order closed. Logged to MoneyDectedButOrderFailed.Admin Will refund you manually after verification. Contact support with recovery ID for faster resolution.',
                    'order_status': order.status,
                    'recovery_id': recovery.id
                },
                status=http_status.HTTP_200_OK
            )

        order.confirm_payment()
        if invoice:
            invoice.status = 'VALID'
            invoice.gateway_status = 'VALID'
            invoice.is_paid = True
            invoice.payment_date = validation.get('tran_date')
            invoice.card_brand = validation.get('card_brand', '')
            invoice.card_issuer = validation.get('card_issuer', '')
            invoice.card_type = validation.get('card_type', '')
            invoice.store_amount = validation.get('store_amount', '')
            invoice.currency = validation.get('currency', '')
            invoice.amount = self._to_decimal(validation.get('amount', 0))
            invoice.risk_level = validation.get('risk_level', '')
            invoice.risk_title = validation.get('risk_title', '')
            invoice.bank_tran_id = validation.get('bank_tran_id', '')
            invoice.val_id = val_id
            invoice.save()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=http_status.HTTP_200_OK)

    def _handle_failure(self, order, invoice, verified_status, val_id):
        """Handle gateway-verified failure statuses."""
        logger.info(
            "Gateway-verified %s for order %s",
            verified_status, order.order_number,
        )
        if order.status not in ['failed', 'cancelled', 'confirmed']:
            order.fail_order(reason=f'Payment {verified_status} via SSLCommerz (gateway-verified)')
        if invoice:
            invoice.status = verified_status
            invoice.gateway_status = verified_status
            invoice.is_paid = False
            invoice.val_id = val_id
            invoice.save()
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=http_status.HTTP_200_OK)

    def _to_decimal(self, value, default='0'):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal(default)

    def _track_money_deducted_for_failed_order(self, order, validation, request_data):
        transaction_id = (
            validation.get('bank_tran_id')
            or request_data.get('bank_tran_id')
            or request_data.get('tran_id')
            or validation.get('val_id')
            or ''
        )
        amount = self._to_decimal(validation.get('amount', 0))
        phone = (
            request_data.get('cus_phone')
            or validation.get('cus_phone')
            or order.phone_number
            or ''
        )
        card_type = (
            validation.get('card_type')
            or validation.get('card_brand')
            or request_data.get('card_type')
            or ''
        )
        reason = (
            f"Gateway status VALID after order already {order.status}. "
            "Manual reconciliation/refund required."
        )

        recovery, _ = MoneyDectedButOrderFailed.objects.update_or_create(
            order=order,
            transaction_id=transaction_id,
            defaults={
                'reason': reason,
                'amount': amount,
                'phone': phone,
                'card_type': card_type,
            }
        )
        return recovery

    def validate_payment(self, val_id):
        validation_url = settings.SSLCOMMERZ_VALIDATION_URL
        params = {
            'val_id': val_id,
            'store_id': settings.STORE_ID,
            'store_passwd': settings.STORE_PASSWORD,
            'format': 'json'
        }
        try:
            response = requests.get(validation_url, params=params, timeout=10)
            # NEW-III-05: Log only status, never full response (contains card data).
            resp_json = response.json()
            logger.info(
                "Validation response for val_id=%s: status=%s",
                val_id, resp_json.get('status', 'unknown'),
            )
            return resp_json
        except Exception as e:
            logger.error("Validation error for val_id=%s: %s", val_id, e)
            return None

