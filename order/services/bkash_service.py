import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = 'bkash_id_token'
TOKEN_EXPIRY_KEY = 'bkash_token_expiry'


class BkashService:
    """
    bKash Payment Gateway (PGW) API client.

    Flow: Grant Token → Create Payment → Execute Payment → Query
    Docs: https://developer.bka.sh/docs
    """

    def __init__(self):
        self.app_key = settings.BKASH_APP_KEY
        self.app_secret = settings.BKASH_APP_SECRET
        self.base_url = settings.BKASH_BASE_URL.rstrip('/')
        self.timeout = 30

    # ── Token Management ──────────────────────────────────────────────

    def _get_headers(self, token=None):
        headers = {
            'Content-Type': 'application/json',
            'X-APP-Key': self.app_key,
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def grant_token(self):
        """POST /token/grant — get a new id_token (valid ~1hr)."""
        url = f'{self.base_url}/token/grant'
        payload = {
            'app_key': self.app_key,
            'app_secret': self.app_secret,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get('statusCode') == '0000':
                token = data['id_token']
                expires_in = data.get('expires_in', 3600)
                # Cache 5 min before actual expiry
                safe_ttl = max(expires_in - 300, 60)
                cache.set(TOKEN_CACHE_KEY, token, safe_ttl)
                cache.set(TOKEN_EXPIRY_KEY, time.time() + expires_in, safe_ttl)
                logger.info("bKash token granted, expires_in=%s", expires_in)
                return token
            else:
                logger.error("bKash grant_token failed: %s", data.get('statusMessage'))
                return None
        except requests.RequestException as e:
            logger.exception("bKash grant_token network error")
            return None

    def _get_valid_token(self):
        """Return a cached token, or grant a new one."""
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        return self.grant_token()

    # ── Create Payment ────────────────────────────────────────────────

    def create_payment(self, payer_reference, amount, merchant_invoice_number):
        """
        POST /checkout/payment/create — initiate a payment.

        Returns dict with keys:
          - success: bool
          - payment_id: str (if success)
          - checkout_url: str (bKash payment page URL, if success)
          - error: str (if failure)
        """
        token = self._get_valid_token()
        if not token:
            return {'success': False, 'error': 'Failed to obtain bKash access token'}

        url = f'{self.base_url}/checkout/payment/create'
        payload = {
            'payerReference': payer_reference,
            'amount': str(amount),
            'currency': 'BDT',
            'intent': 'sale',
            'merchantInvoiceNumber': merchant_invoice_number,
        }

        try:
            resp = requests.post(
                url, json=payload,
                headers=self._get_headers(token),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('statusCode') == '0000':
                logger.info(
                    "bKash payment created: paymentID=%s invoice=%s",
                    data.get('paymentID'), merchant_invoice_number,
                )
                return {
                    'success': True,
                    'payment_id': data['paymentID'],
                    'checkout_url': data['bkashURL'],
                }
            else:
                logger.warning(
                    "bKash create_payment failed: status=%s msg=%s",
                    data.get('statusCode'), data.get('statusMessage'),
                )
                return {'success': False, 'error': data.get('statusMessage', 'Payment creation failed')}

        except requests.RequestException as e:
            logger.exception("bKash create_payment network error for invoice %s", merchant_invoice_number)
            return {'success': False, 'error': 'Payment gateway unreachable'}

    # ── Execute Payment ───────────────────────────────────────────────

    def execute_payment(self, payment_id):
        """
        POST /checkout/payment/execute — finalize payment after customer authorization.

        Must be called on the success callback. Returns:
          - success: bool
          - transaction_status: str
          - amount: str
          - merchant_invoice_number: str
          - error: str (if failure)
        """
        token = self._get_valid_token()
        if not token:
            return {'success': False, 'error': 'Failed to obtain bKash access token'}

        url = f'{self.base_url}/checkout/payment/execute'
        payload = {'paymentID': payment_id}

        try:
            resp = requests.post(
                url, json=payload,
                headers=self._get_headers(token),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('statusCode') == '0000':
                logger.info("bKash payment executed: paymentID=%s status=%s", payment_id, data.get('transactionStatus'))
                return {
                    'success': True,
                    'transaction_status': data.get('transactionStatus', ''),
                    'amount': data.get('amount', '0'),
                    'currency': data.get('currency', 'BDT'),
                    'merchant_invoice_number': data.get('merchantInvoiceNumber', ''),
                    'payment_id': data.get('paymentID', payment_id),
                    'trx_id': data.get('trxID', ''),
                    'payer_reference': data.get('payerReference', ''),
                }
            else:
                logger.warning(
                    "bKash execute_payment failed: paymentID=%s status=%s msg=%s",
                    payment_id, data.get('statusCode'), data.get('statusMessage'),
                )
                return {'success': False, 'error': data.get('statusMessage', 'Payment execution failed')}

        except requests.RequestException as e:
            logger.exception("bKash execute_payment network error for paymentID=%s", payment_id)
            return {'success': False, 'error': 'Payment gateway unreachable'}

    # ── Query Payment Status ──────────────────────────────────────────

    def query_payment(self, payment_id):
        """
        POST /checkout/payment/status — verify payment status.

        Returns dict with success, transaction_status, amount, etc.
        """
        token = self._get_valid_token()
        if not token:
            return {'success': False, 'error': 'Failed to obtain bKash access token'}

        url = f'{self.base_url}/checkout/payment/status'
        payload = {'paymentID': payment_id}

        try:
            resp = requests.post(
                url, json=payload,
                headers=self._get_headers(token),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('statusCode') == '0000':
                return {
                    'success': True,
                    'transaction_status': data.get('transactionStatus', ''),
                    'amount': data.get('amount', '0'),
                    'currency': data.get('currency', 'BDT'),
                    'merchant_invoice_number': data.get('merchantInvoiceNumber', ''),
                    'payment_id': data.get('paymentID', payment_id),
                    'trx_id': data.get('trxID', ''),
                }
            else:
                return {'success': False, 'error': data.get('statusMessage', 'Query failed')}

        except requests.RequestException as e:
            logger.exception("bKash query_payment network error for paymentID=%s", payment_id)
            return {'success': False, 'error': 'Payment gateway unreachable'}

    # ── Refund ────────────────────────────────────────────────────────

    def refund_transaction(self, payment_id, amount, reason='Refund requested'):
        """
        POST /checkout/payment/refund — refund a completed payment.

        Returns dict with success, refund_trx_id, status, error.
        """
        token = self._get_valid_token()
        if not token:
            return {'success': False, 'error': 'Failed to obtain bKash access token'}

        url = f'{self.base_url}/checkout/payment/refund'
        payload = {
            'paymentID': payment_id,
            'amount': str(amount),
            'reason': reason,
        }

        try:
            resp = requests.post(
                url, json=payload,
                headers=self._get_headers(token),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('statusCode') == '0000':
                logger.info("bKash refund success: paymentID=%s refundTrxID=%s", payment_id, data.get('refundTrxID'))
                return {
                    'success': True,
                    'refund_trx_id': data.get('refundTrxID', ''),
                    'status': data.get('statusMessage', ''),
                    'amount': data.get('amount', str(amount)),
                }
            else:
                logger.warning(
                    "bKash refund failed: paymentID=%s status=%s msg=%s",
                    payment_id, data.get('statusCode'), data.get('statusMessage'),
                )
                return {'success': False, 'error': data.get('statusMessage', 'Refund failed')}

        except requests.RequestException as e:
            logger.exception("bKash refund network error for paymentID=%s", payment_id)
            return {'success': False, 'error': 'Payment gateway unreachable'}
