import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SslCommerzService:
    """
    SSLCommerz payment gateway client.

    Handles payment initiation and validation.
    Docs: https://developer.sslcommerz.com/
    """

    def __init__(self):
        self.api_url = settings.SSLCOMMERZ_API_URL
        self.validation_url = settings.SSLCOMMERZ_VALIDATION_URL
        self.store_id = settings.STORE_ID
        self.store_password = settings.STORE_PASSWORD

    def create_payment(self, order, webhook_url, customer_name, customer_email, customer_phone):
        """
        Initiate an SSLCommerz payment.

        Args:
            order: Order instance
            webhook_url: Full URL for SSLCommerz callbacks (success/fail/cancel/ipn)
            customer_name: Sanitized customer name
            customer_email: Customer email
            customer_phone: Customer phone number

        Returns dict:
            - status: 'SUCCESS' or 'FAILED'
            - GatewayPageURL: payment page URL (on success)
            - failedreason: error message (on failure)
        """
        post_data = {
            'store_id': self.store_id,
            'store_passwd': self.store_password,
            'total_amount': float(order.shipping_fee),
            'currency': 'BDT',
            'tran_id': order.order_number,
            'success_url': webhook_url,
            'fail_url': webhook_url,
            'cancel_url': webhook_url,
            'ipn_url': webhook_url,
            'cus_name': customer_name,
            'cus_email': customer_email,
            'cus_add1': order.shipping_address[:50],
            'cus_city': order.shipping_city[:30],
            'cus_postcode': order.shipping_postal_code[:10],
            'cus_country': order.shipping_country[:30],
            'cus_phone': customer_phone,
            'shipping_method': 'NO',
            'product_name': f"Order {order.order_number}"[:50],
            'product_category': 'General',
            'product_profile': 'general',
        }

        try:
            response = requests.post(self.api_url, data=post_data, timeout=15)
            return response.json()
        except Exception as e:
            logger.exception("SSLCommerz create_payment network error for order %s", order.order_number)
            return {'status': 'FAILED', 'failedreason': 'Payment gateway unreachable'}

    def validate_payment(self, val_id):
        """
        Validate a payment via SSLCommerz validation API.

        Args:
            val_id: The validation ID from the IPN callback

        Returns dict with validated payment data, or None on error.
        """
        params = {
            'val_id': val_id,
            'store_id': self.store_id,
            'store_passwd': self.store_password,
            'format': 'json'
        }
        try:
            response = requests.get(self.validation_url, params=params, timeout=10)
            resp_json = response.json()
            logger.info(
                "Validation response for val_id=%s: status=%s",
                val_id, resp_json.get('status', 'unknown'),
            )
            return resp_json
        except Exception as e:
            logger.error("Validation error for val_id=%s: %s", val_id, e)
            return None
