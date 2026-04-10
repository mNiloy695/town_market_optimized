from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status  
from .models import Order
from .serializers import OrderDetailSerializer as OrderSerializer
import requests
from rest_framework.permissions import AllowAny  
class IpnViewWebhookSSLCommerze(APIView):
    # permission_classes = [AllowAny]  

    def post(self, request, *args, **kwargs):
        data = request.data
        val_id = data.get('val_id')
        tran_id = data.get('tran_id')
        currency = data.get('currency')
        amount = data.get('amount')
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

        if payment_status == 'VALID':
            validation = self.validate_payment(val_id)

            if not validation or validation.get('status') != 'VALID':
                order.is_paid = False
                order.status = 'failed'
                order.save()
                return Response(
                    {'error': 'Validation failed'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )

            real_amount = float(validation.get('amount', 0))
            real_currency = validation.get('currency', '')

            if real_amount != float(amount) or real_currency != currency:
                order.is_paid = False
                order.status = 'failed'
                order.save()
                return Response(
                    {'error': 'Amount or currency mismatch!'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )

        
            order.confirm_payment()

            serializer = OrderSerializer(order)
            return Response(serializer.data, status=http_status.HTTP_200_OK)

        
        elif payment_status == 'FAILED':
            order.is_paid = False
            order.status = 'failed'
            order.save()
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=http_status.HTTP_200_OK)

        
        elif payment_status == 'CANCELLED':
            order.is_paid = False
            order.status = 'cancelled'
            order.save()
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=http_status.HTTP_200_OK)

        return Response(
            {'error': 'Unknown status'},
            status=http_status.HTTP_400_BAD_REQUEST
        )

    def validate_payment(self, val_id):
        validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
        params = {
            'val_id': val_id,
            'store_id': 'salah69d86c586754c',
            'store_passwd': 'salah69d86c586754c@ssl',
            'format': 'json'
        }
        try:
            response = requests.get(validation_url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Validation error: {e}")
            return None