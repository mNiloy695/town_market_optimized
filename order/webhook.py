from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status  
from .models import Order,MoneyDectedButOrderFailed
from .serializers import OrderDetailSerializer as OrderSerializer
import requests
from rest_framework.permissions import AllowAny
from invoice.models import Invoice
from django.conf import settings
from decimal import Decimal, InvalidOperation

class IpnViewWebhookSSLCommerze(APIView):
    # permission_classes = [AllowAny]  

    def post(self, request, *args, **kwargs):
        data = request.data
        val_id = data.get('val_id')
        tran_id = data.get('tran_id')
        currency = data.get('currency')
        payment_status = data.get('status') 
        print(f"Received IPN: {data}")

        order = Order.objects.filter(order_number=tran_id).first()

        if not order:
            print(f"Order not found for transaction ID: {tran_id}")
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
            invoice=Invoice.objects.get(order=order)
        except Invoice.DoesNotExist:
            invoice=None

        
        if invoice:
            invoice.is_ipn_verified=True
            invoice.save()

        if payment_status == 'VALID':
            validation = self.validate_payment(val_id)

          


            if not validation or validation.get('status') != 'VALID':
                if order.status not in ['failed', 'cancelled', 'confirmed']:
                    order.fail_order(reason='SSLCommerz validation failed')
                if invoice:
                    invoice.status = 'FAILED'
                    invoice.gateway_status = 'FAILED'
                    invoice.is_paid=False
                    invoice.val_id=val_id
                    invoice.save()
                return Response(
                    {'error': 'Validation failed'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )

            real_amount = self._to_decimal(validation.get('amount', 0))
            real_currency = validation.get('currency', '')
            total_shipping_fee = sum(so.shipping_fee for so in order.shop_orders.all())
            expected_currency = 'BDT'

            if real_amount != total_shipping_fee or real_currency != expected_currency:
                if order.status not in ['failed', 'cancelled', 'confirmed']:
                    order.fail_order(reason='Payment amount/currency mismatch')
                if invoice:
                    invoice.status = 'FAILED'
                    invoice.gateway_status = 'FAILED'
                    invoice.is_paid=False
                    invoice.val_id=val_id
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
                invoice.is_paid=True
                invoice.payment_date=validation.get('tran_date')
                invoice.card_brand=validation.get('card_brand', '')
                invoice.card_issuer=validation.get('card_issuer', '')
                invoice.card_type=validation.get('card_type', '')
                invoice.store_amount=validation.get('store_amount', '')
                invoice.currency=validation.get('currency', '')
                invoice.amount=self._to_decimal(validation.get('amount', 0))
                invoice.risk_level=validation.get('risk_level', '')
                invoice.risk_title=validation.get('risk_title', '')
                invoice.bank_tran_id=validation.get('bank_tran_id', '')
                invoice.val_id=val_id
                invoice.save()

            serializer = OrderSerializer(order)
            return Response(serializer.data, status=http_status.HTTP_200_OK)

        
        elif payment_status in ['FAILED', 'CANCELLED']:
            if order.status not in ['failed', 'cancelled', 'confirmed']:
                order.fail_order(reason=f'Payment {payment_status} via SSLCommerz')
            if invoice:
                invoice.status = payment_status
                invoice.gateway_status = payment_status
                invoice.is_paid=False
                invoice.val_id=val_id
                invoice.save()
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=http_status.HTTP_200_OK)

        return Response(
            {'error': 'Unknown status'},
            status=http_status.HTTP_400_BAD_REQUEST
        )

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
            transction_id=transaction_id,
            defaults={
                'reason': reason,
                'amount': amount,
                'phone': phone,
                'card_type': card_type,
            }
        )
        return recovery

    def validate_payment(self, val_id):
        validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
        params = {
            'val_id': val_id,
            'store_id':settings.STORE_ID,
            'store_passwd': settings.STORE_PASSWORD,
            'format': 'json'
        }
        try:
            response = requests.get(validation_url, params=params, timeout=10)
            print(f"Validation response: {response.text}")
            return response.json()
        except Exception as e:
            print(f"Validation error: {e}")
            return None
