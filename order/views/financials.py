import logging
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from order.models import (
    Order, ShopOrder, FinancialLedgerEntry, MerchantSettlement,
    CommissionPayment, CommissionPaymentLine
)
from shop.models import Shop
from shop.checks import get_vendor_shop

logger = logging.getLogger(__name__)

def paginate_queryset(queryset, request, page_size=20, page_key='page'):
    page = request.query_params.get(page_key, 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    paginator = Paginator(queryset, page_size)
    try:
        paginated_data = paginator.page(page)
    except Exception:
        paginated_data = paginator.page(1)
        page = 1
        
    return {
        'results': paginated_data,
        'page': page,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count
    }

def filter_ledger_queryset(queryset, query_params):
    """Apply ledger list filters from query params (ledger_category / ledger_type / ledger_shop / ledger_search)."""
    entry_type = (query_params.get('ledger_type') or '').strip()
    category = (query_params.get('ledger_category') or '').strip()
    shop = (query_params.get('ledger_shop') or '').strip()
    search = (query_params.get('ledger_search') or '').strip()

    if entry_type in ('debit', 'credit'):
        queryset = queryset.filter(entry_type=entry_type)
    if category:
        queryset = queryset.filter(category=category)
    if shop:
        queryset = queryset.filter(shop__name__icontains=shop)
    if search:
        queryset = queryset.filter(
            Q(notes__icontains=search)
            | Q(reference_id__icontains=search)
            | Q(order__order_number__icontains=search)
            | Q(shop__name__icontains=search)
        )
    return queryset

def serialize_ledger_entry(entry):
    return {
        'id': str(entry.id),
        'entry_type': entry.entry_type,
        'category': entry.category,
        'amount': str(entry.amount),
        'order_number': entry.order.order_number if entry.order else None,
        'shop_order_id': entry.shop_order_id,
        'shop_name': entry.shop.name if entry.shop else None,
        'reference_id': entry.reference_id,
        'notes': entry.notes,
        'created_at': entry.created_at.isoformat(),
        'recorded_by': entry.recorded_by.username if entry.recorded_by else None
    }

def serialize_merchant_ledger_entry(entry):
    """Merchant-facing ledger row enriched with commission/net amounts."""
    data = serialize_ledger_entry(entry)
    so = entry.shop_order
    data['commission_amount'] = str(so.platform_commission) if so and so.platform_commission is not None else '0.00'
    data['net_merchant_amount'] = str(so.merchant_net) if so and so.merchant_net is not None else '0.00'
    return data

def serialize_settlement(settlement):
    return {
        'id': settlement.id,
        'settlement_number': settlement.settlement_number,
        'shop_id': settlement.shop_id,
        'shop_name': settlement.shop.name,
        'amount_product': str(settlement.amount_product),
        'amount_shipping': str(settlement.amount_shipping),
        'total_amount': str(settlement.total_amount),
        'payment_method': settlement.payment_method,
        'transaction_reference': settlement.transaction_reference,
        'status': settlement.status,
        'created_at': settlement.created_at.isoformat(),
        'notes': settlement.notes,
        'orders_count': len(settlement.shop_orders.all())
    }

def serialize_commission_payment(payment):
    lines = payment.lines.select_related('shop_order__order').all()
    if lines:
        allocation = [
            {
                'order_number': line.shop_order.get_order_number(),
                'shop_order_id': line.shop_order_id,
                'amount': str(line.amount),
                'sequence': line.sequence,
            }
            for line in lines
        ]
        applied_order_numbers = [l['order_number'] for l in allocation]
    else:
        # Legacy record: fall back to the M2M set of orders.
        applied_order_numbers = [so.get_order_number() for so in payment.shop_orders.all()]
        allocation = [
            {'order_number': on, 'shop_order_id': None, 'amount': None, 'sequence': i}
            for i, on in enumerate(applied_order_numbers)
        ]
    return {
        'id': payment.id,
        'payment_number': payment.payment_number,
        'shop_id': payment.shop_id,
        'shop_name': payment.shop.name,
        'amount': str(payment.amount),
        'liability_before': str(payment.liability_before),
        'liability_after': str(payment.liability_after),
        'overpaid_amount': str(payment.overpaid_amount),
        'payment_method': payment.payment_method,
        'transaction_reference': payment.transaction_reference,
        'status': payment.status,
        'overpay_credit': payment.overpay_credit,
        'created_at': payment.created_at.isoformat(),
        'notes': payment.notes,
        'orders_count': len(allocation),
        'applied_order_numbers': applied_order_numbers,
        'allocation': allocation
    }

def commission_liability_for_orders(shop_orders):
    """Money the merchant owes for an order = max(0, commission - shipping), gross."""
    return sum(
        max(Decimal('0.00'), so.platform_commission - so.shipping_fee)
        for so in shop_orders
    )

def remaining_commission_liability_for_orders(shop_orders):
    """Money still owed after FIFO-allocated commission payments have been applied."""
    return sum(
        max(
            Decimal('0.00'),
            max(Decimal('0.00'), so.platform_commission - so.shipping_fee) - so.commission_paid
        )
        for so in shop_orders
    )

def commission_paid_for_orders(shop_orders):
    """Total commission amount already allocated (FIFO) against these orders."""
    return sum(so.commission_paid for so in shop_orders)


class AdminFinancialDashboardView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        try:
            # 1. Total Platform Revenue (commission + cancellation charges)
            revenue_categories = [
                FinancialLedgerEntry.Category.PLATFORM_COMMISSION,
                FinancialLedgerEntry.Category.CANCELLATION_CHARGE
            ]
            total_revenue = FinancialLedgerEntry.objects.filter(
                category__in=revenue_categories,
                entry_type=FinancialLedgerEntry.EntryType.CREDIT
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

            # 2. Total Payout Liabilities: Unsettled shipping fees minus platform commission for delivered unsettled shop orders.
            unsettled_delivered = ShopOrder.objects.filter(
                status='delivered',
                settlement_status='unsettled'
            )
            total_liabilities = sum(so.shipping_fee - so.platform_commission for so in unsettled_delivered)
            
            # 3. Total Paid Out
            total_paid_out = MerchantSettlement.objects.filter(
                status='processed'
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            
            # 4. Total Commissions (earned, just platform commission, not including cancellation charges)
            total_commissions = FinancialLedgerEntry.objects.filter(
                category=FinancialLedgerEntry.Category.PLATFORM_COMMISSION,
                entry_type=FinancialLedgerEntry.EntryType.CREDIT
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

            # 4b. Total commission money received from merchants (CommissionPayment)
            total_commission_received = FinancialLedgerEntry.objects.filter(
                category=FinancialLedgerEntry.Category.COMMISSION_PAYMENT,
                entry_type=FinancialLedgerEntry.EntryType.DEBIT
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

            # 4c. Paginated ledger entries (filters + pagination via ledger_* params)
            ledger_qs = FinancialLedgerEntry.objects.select_related('order', 'shop', 'recorded_by').order_by('-created_at')
            ledger_qs = filter_ledger_queryset(ledger_qs, request.query_params)
            paginated_ledger = paginate_queryset(ledger_qs, request, page_key='ledger_page')
            serialized_ledger = [serialize_ledger_entry(e) for e in paginated_ledger['results']]

            # 5. Settlements
            settlements_qs = MerchantSettlement.objects.select_related('shop').prefetch_related('shop_orders').order_by('-created_at')
            paginated_settlements = paginate_queryset(settlements_qs, request)
            serialized_settlements = [serialize_settlement(s) for s in paginated_settlements['results']]

            # 5b. Commission payments (Merchant -> Platform), audit trail
            commission_qs = CommissionPayment.objects.select_related('shop').prefetch_related(
                'lines__shop_order__order', 'shop_orders'
            ).order_by('-created_at')
            paginated_commissions = paginate_queryset(commission_qs, request)
            serialized_commissions = [serialize_commission_payment(c) for c in paginated_commissions['results']]

            # 6. Unsettled Shops list (for convenient settling)
            unsettled_shops_data = []
            unsettled_shops = Shop.objects.filter(
                orders__status='delivered',
                orders__settlement_status='unsettled',
                is_active=True,
                is_deactivated=False
            ).distinct().order_by('name')

            # Single query for all unsettled delivered orders, grouped in memory
            # to avoid the per-shop N+1 aggregate queries.
            orders_by_shop = {}
            unsettled_orders = ShopOrder.objects.filter(
                shop__in=unsettled_shops,
                status='delivered',
                settlement_status='unsettled'
            ).select_related('shop')
            for so in unsettled_orders:
                orders_by_shop.setdefault(so.shop_id, []).append(so)

            for shop in unsettled_shops:
                orders = orders_by_shop.get(shop.id, [])
                shipping_sum = sum(so.shipping_fee for so in orders) or Decimal('0.00')
                comm_sum = sum(so.platform_commission for so in orders) or Decimal('0.00')
                net_payout = shipping_sum - comm_sum
                commission_liability = commission_liability_for_orders(orders)
                commission_paid = commission_paid_for_orders(orders)
                remaining_commission_liability = remaining_commission_liability_for_orders(orders)

                # Skip merchants with nothing left to do: no payout owed to them
                # and no commission due from them.
                if net_payout <= 0 and remaining_commission_liability <= 0:
                    continue

                unsettled_shops_data.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'unsettled_orders_count': len(orders),
                    'shipping_fees': str(shipping_sum),
                    'commissions': str(comm_sum),
                    'net_payout': str(net_payout),
                    'commission_liability': str(commission_liability),
                    'commission_paid': str(commission_paid),
                    'remaining_commission_liability': str(remaining_commission_liability),
                    'has_settle_due': net_payout > 0,
                    'has_collect_due': remaining_commission_liability > 0
                })

            return Response({
                'total_revenue': str(total_revenue),
                'total_commissions': str(total_commissions),
                'total_commission_received': str(total_commission_received),
                'unsettled_merchant_liabilities': str(total_liabilities),
                'total_paid_out': str(total_paid_out),
                'ledger': {
                    'results': serialized_ledger,
                    'page': paginated_ledger['page'],
                    'total_pages': paginated_ledger['total_pages'],
                    'total_count': paginated_ledger['total_count']
                },
                'settlements': {
                    'results': serialized_settlements,
                    'page': paginated_settlements['page'],
                    'total_pages': paginated_settlements['total_pages'],
                    'total_count': paginated_settlements['total_count']
                },
                'commission_payments': {
                    'results': serialized_commissions,
                    'page': paginated_commissions['page'],
                    'total_pages': paginated_commissions['total_pages'],
                    'total_count': paginated_commissions['total_count']
                },
                'unsettled_shops': unsettled_shops_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.exception("Admin financial dashboard failed")
            return Response(
                {'error': 'Internal server error while retrieving financial stats.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MerchantFinancialDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            shop = get_vendor_shop(request.user)
        except Exception:
            return Response(
                {'error': 'You do not own an approved/active shop.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # 1. Total Earned (delivered orders: subtotal + shipping_fee)
            delivered_orders = ShopOrder.objects.filter(shop=shop, status='delivered')
            
            # Using custom sum logic to avoid complex annotation/aggregate on F expressions
            total_earned = sum((so.merchant_net + so.shipping_fee) for so in delivered_orders)

            # 2. Commissions Deducted
            commission_deducted = delivered_orders.aggregate(Sum('platform_commission'))['platform_commission__sum'] or Decimal('0.00')

            # 3. Unsettled Balance (delivered, unsettled: shipping_fee - platform_commission)
            unsettled_orders = list(delivered_orders.filter(settlement_status='unsettled'))
            unsettled_balance = sum(so.shipping_fee - so.platform_commission for so in unsettled_orders)

            # 3b. Commission liability (money merchant owes platform) and payments already made
            commission_liability = commission_liability_for_orders(unsettled_orders)
            commission_paid = commission_paid_for_orders(unsettled_orders)
            remaining_commission_liability = remaining_commission_liability_for_orders(unsettled_orders)

            # 4. Total Settled
            total_settled = MerchantSettlement.objects.filter(
                shop=shop,
                status='processed'
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

            # 5. Ledger entries (filters + pagination via ledger_* params)
            ledger_qs = FinancialLedgerEntry.objects.filter(shop=shop).select_related(
                'order', 'shop', 'shop_order', 'recorded_by'
            ).order_by('-created_at')
            ledger_qs = filter_ledger_queryset(ledger_qs, request.query_params)
            paginated_ledger = paginate_queryset(ledger_qs, request, page_key='ledger_page')
            serialized_ledger = [serialize_merchant_ledger_entry(e) for e in paginated_ledger['results']]

            # 6. Settlements
            settlements_qs = MerchantSettlement.objects.filter(shop=shop).select_related('shop').prefetch_related('shop_orders').order_by('-created_at')
            paginated_settlements = paginate_queryset(settlements_qs, request)
            serialized_settlements = [serialize_settlement(s) for s in paginated_settlements['results']]

            # 6b. Commission payments (Merchant -> Platform)
            commission_qs = CommissionPayment.objects.filter(shop=shop).select_related('shop').prefetch_related(
                'lines__shop_order__order', 'shop_orders'
            ).order_by('-created_at')
            paginated_commissions = paginate_queryset(commission_qs, request)
            serialized_commissions = [serialize_commission_payment(c) for c in paginated_commissions['results']]

            return Response({
                'total_revenue': str(total_earned),
                'commission_deducted': str(commission_deducted),
                'unsettled_balance': str(unsettled_balance),
                'commission_liability': str(commission_liability),
                'commission_paid': str(commission_paid),
                'remaining_commission_liability': str(remaining_commission_liability),
                'paid_amount': str(total_settled),
                'recent_ledger_entries': serialized_ledger,
                'ledger': {
                    'results': serialized_ledger,
                    'page': paginated_ledger['page'],
                    'total_pages': paginated_ledger['total_pages'],
                    'total_count': paginated_ledger['total_count']
                },
                'settlements': {
                    'results': serialized_settlements,
                    'page': paginated_settlements['page'],
                    'total_pages': paginated_settlements['total_pages'],
                    'total_count': paginated_settlements['total_count']
                },
                'commission_payments': {
                    'results': serialized_commissions,
                    'page': paginated_commissions['page'],
                    'total_pages': paginated_commissions['total_pages'],
                    'total_count': paginated_commissions['total_count']
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Merchant financial dashboard failed for user %s", request.user.id)
            return Response(
                {'error': 'Internal server error while retrieving financial stats.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminCreateSettlementView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        shop_id = request.data.get('shop_id')
        shop_order_ids = request.data.get('shop_order_ids')
        payment_method = request.data.get('payment_method', 'bank_transfer')
        transaction_reference = request.data.get('transaction_reference', '')
        notes = request.data.get('notes', '')

        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop = get_object_or_404(Shop, id=shop_id)

        try:
            with transaction.atomic():
                # 1. Fetch unsettled, delivered shop orders for this shop using select_for_update
                orders_qs = ShopOrder.objects.select_for_update().filter(
                    shop=shop,
                    status='delivered',
                    settlement_status='unsettled'
                )

                if shop_order_ids:
                    orders_qs = orders_qs.filter(id__in=shop_order_ids)

                shop_orders = list(orders_qs)

                if not shop_orders:
                    return Response(
                        {'error': 'No unsettled delivered shop orders found to settle.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 2. Sum up fields
                total_shipping = sum(so.shipping_fee for so in shop_orders)
                total_commission = sum(so.platform_commission for so in shop_orders)
                net_payout = total_shipping - total_commission

                # Guard: a negative payout is a merchant debt to the platform, not a payout.
                if net_payout < 0:
                    return Response(
                        {
                            'error': (
                                f"Selected orders have TK {(-net_payout):.2f} in commission "
                                "exceeding shipping fees, so the merchant owes the platform. "
                                "Record this as a commission payment instead of a payout."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Create the settlement record
                settlement = MerchantSettlement.objects.create(
                    shop=shop,
                    amount_product=Decimal('0.00'),
                    amount_shipping=net_payout,
                    payment_method=payment_method,
                    transaction_reference=transaction_reference,
                    status='processed',
                    recorded_by=request.user,
                    notes=notes or f"Settlement for {len(shop_orders)} shop orders."
                )

                # Link all shop orders
                settlement.shop_orders.add(*shop_orders)

                # Mark all shop orders as settled
                for so in shop_orders:
                    so.settlement_status = 'settled'
                    so.save(update_fields=['settlement_status'])

                # Log the ledger entry
                FinancialLedgerEntry.log_settlement(
                    settlement=settlement,
                    recorded_by=request.user
                )

                return Response({
                    'message': f"Settlement processed successfully for shop {shop.name}",
                    'settlement': serialize_settlement(settlement)
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Merchant settlement failed for shop %s", shop_id)
            return Response(
                {'error': 'Failed to process settlement due to an internal error.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminCreateCommissionPaymentView(APIView):
    """Record a Merchant -> Platform commission payment.

    Mirrors AdminCreateSettlementView but in the opposite direction. It never
    flips ShopOrder.settlement_status: that flag exclusively means the platform
    paid the merchant out.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """Paginated full transaction history with optional filters (audit trail)."""
        qs = CommissionPayment.objects.select_related('shop', 'recorded_by').prefetch_related(
            'lines__shop_order__order', 'shop_orders'
        ).order_by('-created_at')

        shop_name = request.query_params.get('shop')
        if shop_name:
            qs = qs.filter(shop__name__icontains=shop_name)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        method = request.query_params.get('payment_method')
        if method:
            qs = qs.filter(payment_method__icontains=method)
        reference = request.query_params.get('reference')
        if reference:
            qs = qs.filter(transaction_reference__icontains=reference)
        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        paginated = paginate_queryset(qs, request)
        serialized = [serialize_commission_payment(c) for c in paginated['results']]
        return Response({
            'results': serialized,
            'page': paginated['page'],
            'total_pages': paginated['total_pages'],
            'total_count': paginated['total_count']
        }, status=status.HTTP_200_OK)

    def post(self, request):
        shop_id = request.data.get('shop_id')
        shop_order_ids = request.data.get('shop_order_ids')
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'manual')
        transaction_reference = request.data.get('transaction_reference', '').strip()
        overpay_credit = request.data.get('overpay_credit', False)
        notes = request.data.get('notes', '')

        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not amount:
            return Response(
                {'error': 'amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(amount))
        except Exception:
            return Response(
                {'error': 'amount must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {'error': 'amount must be greater than zero.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not transaction_reference:
            return Response(
                {'error': 'transaction_reference is required for idempotency.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Duplicate reference prevention (idempotency)
        if CommissionPayment.objects.filter(
            shop=shop,
            transaction_reference=transaction_reference,
            status__in=['received', 'processing']
        ).exists():
            return Response(
                {'error': f'A commission payment with reference "{transaction_reference}" already exists.'},
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                orders_qs = ShopOrder.objects.select_for_update().filter(
                    shop=shop,
                    status='delivered',
                    settlement_status='unsettled'
                )

                if shop_order_ids:
                    orders_qs = orders_qs.filter(id__in=shop_order_ids)

                # FIFO: offset the oldest unsettled delivered orders first.
                shop_orders = list(orders_qs.order_by('delivered_at', 'created_at'))

                if not shop_orders:
                    return Response(
                        {'error': 'No unsettled delivered shop orders found for this shop.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Overpayment is rejected by default: amount cannot exceed the
                # current remaining liability unless overpay_credit=true.
                liability_before = remaining_commission_liability_for_orders(shop_orders)
                if liability_before <= 0:
                    return Response(
                        {
                            'error': (
                                'This shop does not owe any commission on the selected orders '
                                '(shipping fees already cover or exceed commissions).'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                overpay = amount > liability_before
                if overpay and not overpay_credit:
                    return Response(
                        {
                            'error': (
                                f'Amount TK {amount:.2f} exceeds the current commission '
                                f'liability of TK {liability_before:.2f}. '
                                'Set overpay_credit=true to record the excess as merchant credit.'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # FIFO allocation: apply `amount` to oldest orders first, in chunks
                # not exceeding each order's remaining commission debt.
                applied = []
                remaining_amount = amount
                sequence = 0
                for so in shop_orders:
                    if remaining_amount <= 0:
                        break
                    debt = max(Decimal('0.00'), so.platform_commission - so.shipping_fee)
                    order_remaining = max(Decimal('0.00'), debt - so.commission_paid)
                    if order_remaining <= 0:
                        continue
                    alloc = min(remaining_amount, order_remaining)
                    so.commission_paid += alloc
                    so.save(update_fields=['commission_paid'])
                    applied.append((so, alloc, sequence))
                    remaining_amount -= alloc
                    sequence += 1

                allocated_total = amount - remaining_amount
                liability_after = max(
                    Decimal('0.00'), liability_before - allocated_total
                )
                overpaid_amount = max(Decimal('0.00'), remaining_amount)

                payment = CommissionPayment.objects.create(
                    shop=shop,
                    amount=amount,
                    liability_before=liability_before,
                    liability_after=liability_after,
                    overpaid_amount=overpaid_amount,
                    payment_method=payment_method,
                    transaction_reference=transaction_reference,
                    status='received',
                    overpay_credit=overpay_credit,
                    recorded_by=request.user,
                    notes=notes or (
                        f"Commission payment of TK {amount:.2f} received from {shop.name}. "
                        f"Liability {liability_before:.2f} -> {liability_after:.2f}. "
                        f"Applied FIFO to {len(applied)} order(s)."
                    )
                )

                # Link the orders this payment was actually offset against
                # via explicit line-level allocations (FIFO audit trail).
                CommissionPaymentLine.objects.bulk_create([
                    CommissionPaymentLine(
                        payment=payment,
                        shop_order=so,
                        shop=shop,
                        amount=alloc,
                        sequence=seq
                    )
                    for so, alloc, seq in applied
                ])

                # Immutable ledger record
                FinancialLedgerEntry.log_commission_payment(
                    payment=payment,
                    recorded_by=request.user
                )

                return Response({
                    'message': (
                        f"Commission payment of TK {amount:.2f} recorded for shop {shop.name}"
                    ),
                    'commission_payment': serialize_commission_payment(payment)
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Commission payment failed for shop %s", shop_id)
            return Response(
                {'error': 'Failed to record commission payment due to an internal error.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
