import logging
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from order.models import Order, ShopOrder, FinancialLedgerEntry, MerchantSettlement
from shop.models import Shop
from shop.checks import get_vendor_shop

logger = logging.getLogger(__name__)

def paginate_queryset(queryset, request, page_size=20):
    page = request.query_params.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    paginator = Paginator(queryset, page_size)
    try:
        paginated_data = paginator.page(page)
    except Exception:
        paginated_data = paginator.page(1)
        
    return {
        'results': paginated_data,
        'page': page,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count
    }

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
        'orders_count': settlement.shop_orders.count()
    }


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

            # 4. Paginated Ledger entries
            ledger_qs = FinancialLedgerEntry.objects.select_related('order', 'shop', 'recorded_by').all()
            paginated_ledger = paginate_queryset(ledger_qs, request)
            serialized_ledger = [serialize_ledger_entry(e) for e in paginated_ledger['results']]

            # 5. Settlements
            settlements_qs = MerchantSettlement.objects.select_related('shop').all()
            paginated_settlements = paginate_queryset(settlements_qs, request)
            serialized_settlements = [serialize_settlement(s) for s in paginated_settlements['results']]

            # 6. Unsettled Shops list (for convenient settling)
            unsettled_shops_data = []
            unsettled_shops = Shop.objects.filter(
                orders__status='delivered',
                orders__settlement_status='unsettled'
            ).distinct()
            
            for shop in unsettled_shops:
                orders = ShopOrder.objects.filter(
                    shop=shop,
                    status='delivered',
                    settlement_status='unsettled'
                )
                shipping_sum = orders.aggregate(Sum('shipping_fee'))['shipping_fee__sum'] or Decimal('0.00')
                comm_sum = orders.aggregate(Sum('platform_commission'))['platform_commission__sum'] or Decimal('0.00')
                net_payout = shipping_sum - comm_sum
                
                unsettled_shops_data.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'unsettled_orders_count': orders.count(),
                    'shipping_fees': str(shipping_sum),
                    'commissions': str(comm_sum),
                    'net_payout': str(net_payout)
                })

            return Response({
                'stats': {
                    'total_revenue': str(total_revenue),
                    'total_liabilities': str(total_liabilities),
                    'total_paid_out': str(total_paid_out)
                },
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
            unsettled_orders = delivered_orders.filter(settlement_status='unsettled')
            unsettled_balance = sum(so.shipping_fee - so.platform_commission for so in unsettled_orders)

            # 4. Total Settled
            total_settled = MerchantSettlement.objects.filter(
                shop=shop,
                status='processed'
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

            # 5. Ledger entries
            ledger_qs = FinancialLedgerEntry.objects.filter(shop=shop).select_related('order', 'shop', 'recorded_by')
            paginated_ledger = paginate_queryset(ledger_qs, request)
            serialized_ledger = [serialize_ledger_entry(e) for e in paginated_ledger['results']]

            # 6. Settlements
            settlements_qs = MerchantSettlement.objects.filter(shop=shop)
            paginated_settlements = paginate_queryset(settlements_qs, request)
            serialized_settlements = [serialize_settlement(s) for s in paginated_settlements['results']]

            return Response({
                'stats': {
                    'total_earned': str(total_earned),
                    'commission_deducted': str(commission_deducted),
                    'unsettled_balance': str(unsettled_balance),
                    'total_settled': str(total_settled)
                },
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
