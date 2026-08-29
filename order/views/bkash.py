import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import redirect
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from invoice.models import Invoice
from order.models import Order, MoneyDectedButOrderFailed
from order.services.bkash_service import BkashService

logger = logging.getLogger(__name__)


class BkashSuccessCallbackView(APIView):
    """
    bKash success callback.

    bKash redirects the customer here after successful PIN entry.
    We must call execute_payment() to finalize the transaction,
    then confirm the order.

    This endpoint is hit as a GET redirect by the browser.
    We respond with a redirect to the frontend success page.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, payment_id):
        return self._handle(payment_id, request)

    def post(self, request, payment_id):
        return self._handle(payment_id, request)

    def _handle(self, payment_id, request):
        if not payment_id:
            logger.warning("bKash success callback without payment_id")
            return redirect('/payment/failed?error=missing_payment_id')

        # 1. Pre-execution idempotency check
        invoice = Invoice.objects.filter(val_id=payment_id).first()
        if invoice and (invoice.is_paid or (invoice.order and invoice.order.is_paid)):
            return redirect(f'/payment/success?order_number={invoice.order.order_number}')

        bkash = BkashService()
        result = bkash.execute_payment(payment_id)

        if not result.get('success'):
            logger.warning(
                "bKash execute_payment failed: paymentID=%s error=%s",
                payment_id, result.get('error'),
            )
            # Double-check: in case another thread processed it after our check above
            invoice = Invoice.objects.filter(val_id=payment_id).first()
            if invoice and (invoice.is_paid or (invoice.order and invoice.order.is_paid)):
                return redirect(f'/payment/success?order_number={invoice.order.order_number}')
            # Execute failed — order stays pending_payment, Celery task will clean up
            return redirect(f'/payment/failed?error=payment_execution_failed&payment_id={payment_id}')

        invoice_number = result.get('merchant_invoice_number', '')
        order = Order.objects.filter(order_number=invoice_number).first()

        if not order:
            logger.error(
                "bKash success: order not found for invoice=%s paymentID=%s",
                invoice_number, payment_id,
            )
            return redirect('/payment/failed?error=order_not_found')

        # Idempotency — already confirmed
        if order.is_paid:
            return redirect(f'/payment/success?order_number={order.order_number}')

        # Verify amount
        try:
            paid_amount = Decimal(str(result.get('amount', '0')))
        except (InvalidOperation, TypeError, ValueError):
            paid_amount = Decimal('0')

        if paid_amount != order.shipping_fee:
            logger.warning(
                "bKash amount mismatch: order=%s expected=%s got=%s",
                order.order_number, order.shipping_fee, paid_amount,
            )
            order.fail_order(reason='bKash payment amount mismatch')

            MoneyDectedButOrderFailed.objects.update_or_create(
                order=order,
                transaction_id=result.get('trx_id', '') or payment_id,
                defaults={
                    'reason': 'bKash amount mismatch after execute_payment — manual reconciliation/refund required',
                    'amount': paid_amount,
                    'phone': order.phone_number,
                    'card_type': 'bkash',
                },
            )
            try:
                invoice = Invoice.objects.filter(order=order).order_by('-created_at').first()
            except Invoice.DoesNotExist:
                invoice = None
            if invoice:
                invoice.status = 'MONEY_DEDUCTED_ORDER_FAILED'
                invoice.gateway_status = 'SUCCESS'
                invoice.is_paid = False
                invoice.val_id = payment_id
                invoice.bank_tran_id = result.get('trx_id', '')
                invoice.card_type = 'bkash'
                invoice.amount = paid_amount
                invoice.currency = result.get('currency', 'BDT')
                invoice.save()
            return redirect(f'/payment/failed?error=amount_mismatch&order_number={order.order_number}')

        # Confirm payment inside transaction
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order.id)
                if order.is_paid:
                    return redirect(f'/payment/success?order_number={order.order_number}')

                order.confirm_payment()

                # Update invoice
                try:
                    invoice = Invoice.objects.select_for_update().get(order=order)
                except Invoice.DoesNotExist:
                    invoice = None

                if invoice:
                    invoice.status = 'VALID'
                    invoice.gateway_status = 'SUCCESS'
                    invoice.is_paid = True
                    invoice.is_ipn_verified = True
                    invoice.val_id = payment_id
                    invoice.bank_tran_id = result.get('trx_id', '')
                    invoice.card_type = 'bkash'
                    invoice.amount = paid_amount
                    invoice.currency = result.get('currency', 'BDT')
                    invoice.payment_date = order.confirmed_at
                    invoice.save()

                logger.info(
                    "bKash payment confirmed: order=%s paymentID=%s trxID=%s",
                    order.order_number, payment_id, result.get('trx_id'),
                )
        except Exception as e:
            logger.exception("bKash confirmation error for paymentID=%s", payment_id)
            if order.status not in ['confirmed', 'cancelled', 'failed']:
                order.fail_order(reason='bKash confirmation error')
            MoneyDectedButOrderFailed.objects.update_or_create(
                order=order,
                transaction_id=result.get('trx_id', '') or payment_id,
                defaults={
                    'reason': 'bKash execute_payment succeeded but order confirmation failed',
                    'amount': paid_amount,
                    'phone': order.phone_number,
                    'card_type': 'bkash',
                },
            )
            return redirect(f'/payment/failed?error=confirmation_error&order_number={order.order_number}')

        return redirect(f'/payment/success?order_number={order.order_number}')


class BkashFailCallbackView(APIView):
    """
    bKash fail callback.

    Customer failed to complete payment or bKash rejected it.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, payment_id):
        return self._handle(payment_id)

    def post(self, request, payment_id):
        return self._handle(payment_id)

    def _handle(self, payment_id):
        if not payment_id:
            return redirect('/payment/failed?error=missing_payment_id')

        # Try to find order via bKash query
        bkash = BkashService()
        query_result = bkash.query_payment(payment_id)
        invoice_number = query_result.get('merchant_invoice_number', '') if query_result.get('success') else ''

        if invoice_number:
            order = Order.objects.filter(order_number=invoice_number).first()
            if order and order.status not in ['failed', 'cancelled', 'confirmed']:
                order.fail_order(reason='bKash payment failed via callback')

        return redirect(f'/payment/failed?error=payment_failed&payment_id={payment_id}')


class BkashCancelCallbackView(APIView):
    """
    bKash cancel callback.

    Customer cancelled the payment on bKash page.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, payment_id):
        return self._handle(payment_id)

    def post(self, request, payment_id):
        return self._handle(payment_id)

    def _handle(self, payment_id):
        if not payment_id:
            return redirect('/payment/failed?error=missing_payment_id')

        bkash = BkashService()
        query_result = bkash.query_payment(payment_id)
        invoice_number = query_result.get('merchant_invoice_number', '') if query_result.get('success') else ''

        if invoice_number:
            order = Order.objects.filter(order_number=invoice_number).first()
            if order and order.status not in ['failed', 'cancelled', 'confirmed']:
                order.fail_order(reason='bKash payment cancelled by customer')

        return redirect(f'/payment/failed?error=payment_cancelled&payment_id={payment_id}')
