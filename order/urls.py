from django.urls import path

from order.webhook import IpnViewWebhookSSLCommerze
from .views import (
    CheckoutView,
    OrderListView,
    OrderDetailView,
    VendorOrderListView,
    VendorOrderDetailView,
    VendorOrderStatusUpdateView,
    VendorDashboardStatsView,
    CustomerOrderCancel,
    PaymentConfirmationView,
    OrderReturnRequestView,
    VendorReturnApprovalView
)

app_name = 'order'

urlpatterns = [
    # Customer endpoints
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('list/', OrderListView.as_view(), name='order-list'),
    path('<int:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    # path('<int:order_id>/confirm-payment/', PaymentConfirmationView.as_view(), name='confirm-payment'),
    # path('shop-order/<int:shop_order_id>/cancel/', CustomerOrderCancel.as_view(), name='cancel-order'),
    # path('shop-order/<int:shop_order_id>/return/', OrderReturnRequestView.as_view(), name='request-return'),
    
    # Vendor endpoints
    path('vendor/orders/', VendorOrderListView.as_view(), name='vendor-order-list'),
    path('vendor/orders/<int:shop_order_id>/', VendorOrderDetailView.as_view(), name='vendor-order-detail'),
    path('vendor/orders/<int:shop_order_id>/status/', VendorOrderStatusUpdateView.as_view(), name='vendor-order-status'),
    path('vendor/orders/<int:shop_order_id>/return-approval/', VendorReturnApprovalView.as_view(), name='vendor-return-approval'),
    path('vendor/stats/', VendorDashboardStatsView.as_view(), name='vendor-stats'),
    #webhook for sslcommerz payment gateway
    path('webhook/sslcommerz/', IpnViewWebhookSSLCommerze.as_view(), name='sslcommerz-webhook'),
]