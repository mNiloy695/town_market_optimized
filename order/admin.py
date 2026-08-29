from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Order, ShopOrder, OrderItem, OrderTimeline, RefundRecord
)


class OrderItemInline(admin.TabularInline):
    """Inline admin for OrderItems within ShopOrder"""
    model = OrderItem
    extra = 0
    readonly_fields = ('product_variant', 'price_at_purchase', 'quantity', 'line_total')
    fields = ('product_variant', 'price_at_purchase', 'quantity', 'line_total', 'status')
    can_delete = False


class OrderTimelineInline(admin.TabularInline):
    """Inline admin for OrderTimeline within ShopOrder"""
    model = OrderTimeline
    extra = 0
    readonly_fields = ('action', 'description', 'created_at', 'created_by')
    fields = ('action', 'description', 'created_at', 'created_by')
    can_delete = False


class ShopOrderInline(admin.TabularInline):
    """Inline admin for ShopOrders within Order"""
    model = ShopOrder
    extra = 0
    readonly_fields = ('shop', 'total', 'status', 'created_at')
    fields = ('shop', 'total', 'status', 'created_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin configuration for Orders"""
    list_display = ('order_number', 'user_display', 'total_amount', 'status', 'payment_method', 'shop_count', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at', 'is_paid')
    search_fields = ('order_number', 'user__phone', 'user__name')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'get_total_items')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'total_amount', 'status', 'created_at', 'updated_at')
        }),
        ('Shipping Details', {
            'fields': ('shipping_address', 'shipping_city', 'shipping_postal_code', 'shipping_country', 'phone_number')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'is_paid')
        }),
    )
    
    inlines = [ShopOrderInline]
    
    def user_display(self, obj):
        return f"{obj.user.name} ({obj.user.phone})"
    user_display.short_description = 'Customer'
    
    def shop_count(self, obj):
        return obj.shop_orders.count()
    shop_count.short_description = 'Shops'
    
    def get_total_items(self, obj):
        total = sum(order.items.count() for order in obj.shop_orders.all())
        return total
    get_total_items.short_description = 'Total Items'


@admin.register(ShopOrder)
class ShopOrderAdmin(admin.ModelAdmin):
    """Admin configuration for ShopOrders"""
    list_display = ('id', 'shop_name', 'order_number_display', 'total_display', 'status_badge', 'commission_given', 'created_at_display')
    list_filter = ('status', 'commission_given', 'shop', 'created_at')
    list_editable = ('commission_given',)
    search_fields = ('shop__name', 'order__order_number', 'order__user__name')
    readonly_fields = ('order_number_display', 'created_at', 'updated_at', 'get_items_count')
    
    actions = ['mark_commission_paid', 'mark_commission_unpaid']
    
    @admin.action(description="Mark selected orders as commission paid")
    def mark_commission_paid(self, request, queryset):
        updated = queryset.update(commission_given=True)
        self.message_user(request, f"{updated} shop orders marked as commission paid.")
        
    @admin.action(description="Mark selected orders as commission unpaid")
    def mark_commission_unpaid(self, request, queryset):
        updated = queryset.update(commission_given=False)
        self.message_user(request, f"{updated} shop orders marked as commission unpaid.")

    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'shop', 'order_number_display')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'tax', 'shipping_fee', 'discount', 'total', 'commission_given'),
            'classes': ('wide',)
        }),
        ('Status & Tracking', {
            'fields': ('status', 'tracking_number', 'notes'),
            'classes': ('wide',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderTimelineInline]
    
    def shop_name(self, obj):
        return obj.shop.name
    shop_name.short_description = 'Shop'
    shop_name.admin_order_field = 'shop__name'
    
    def order_number_display(self, obj):
        return obj.get_order_number()
    order_number_display.short_description = 'Order Number'
    
    def total_display(self, obj):
        return f"₨ {obj.total:,.2f}"
    total_display.short_description = 'Total'
    total_display.admin_order_field = 'total'
    
    def status_badge(self, obj):
        """Color-coded status badge"""
        status_colors = {
            'pending': '#FFC107',
            'confirmed': '#2196F3',
            'processing': '#FF5722',
            'shipped': '#4CAF50',
            'delivered': '#8BC34A',
            'cancelled': '#F44336',
            'return_requested': '#FF9800',
            'returned': '#9C27B0',
        }
        color = status_colors.get(obj.status, '#757575')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def created_at_display(self, obj):
        return obj.created_at.strftime('%d %b %Y %H:%M')
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    def get_items_count(self, obj):
        return obj.items.count()
    get_items_count.short_description = 'Items'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin configuration for OrderItems"""
    list_display = ('id', 'shop_order', 'product_display', 'quantity', 'price_at_purchase', 'line_total', 'status')
    list_filter = ('status', 'shop_order__created_at')
    search_fields = ('product_variant__product__name', 'shop_order__order__order_number')
    readonly_fields = ('price_at_purchase', 'line_total', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Item Information', {
            'fields': ('shop_order', 'product_variant', 'price_at_purchase', 'quantity')
        }),
        ('Totals', {
            'fields': ('line_total',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def product_display(self, obj):
        return obj.product_variant.product.name
    product_display.short_description = 'Product'
    product_display.admin_order_field = 'product_variant__product__name'


@admin.register(OrderTimeline)
class OrderTimelineAdmin(admin.ModelAdmin):
    """Admin configuration for OrderTimeline"""
    list_display = ('shop_order', 'action_display', 'created_at_display', 'created_by_display')
    list_filter = ('action', 'created_at')
    search_fields = ('shop_order__order__order_number', 'description')
    readonly_fields = ('created_at', 'shop_order', 'action', 'created_by')
    
    fieldsets = (
        ('Timeline Information', {
            'fields': ('shop_order', 'action', 'description')
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    can_delete = False
    
    def action_display(self, obj):
        action_labels = {
            'created': '✓ Created',
            'confirmed': '✓ Confirmed',
            'processing': '⟳ Processing',
            'shipped': '📦 Shipped',
            'delivered': '✓ Delivered',
            'cancelled': '✗ Cancelled',
            'payment_processed': '💳 Payment',
            'return_requested': '↩ Return Requested',
            'returned': '↩ Returned',
        }
        return action_labels.get(obj.action, obj.action)
    action_display.short_description = 'Action'
    
    def created_at_display(self, obj):
        return obj.created_at.strftime('%d %b %Y %H:%M:%S')
    created_at_display.short_description = 'Date'
    
    def created_by_display(self, obj):
        if obj.created_by:
            return f"{obj.created_by.name} ({obj.created_by.phone})"
        return "System"
    created_by_display.short_description = 'Created By'



from .models import MoneyDectedButOrderFailed, RefundRecord

@admin.register(MoneyDectedButOrderFailed)
class MoneyDectedButOrderFailedAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'transaction_id', 'created_at')
    search_fields = ('order__order_number', 'transaction_id', 'phone')
    readonly_fields = (
        'order', 'amount', 'transaction_id', 'phone',
        'card_type', 'reason', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Detection Information', {
            'fields': ('order', 'amount', 'transaction_id', 'phone', 'card_type', 'reason')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    can_delete = False


@admin.register(RefundRecord)
class RefundRecordAdmin(admin.ModelAdmin):
    """Manual-reconciliation queue for refunds (initiated by an operator).
    Refunds are never executed automatically — the operator uses the stored
    gateway transaction id to initiate the refund at the payment provider.
    """
    list_display = (
        'id', 'order', 'gateway', 'amount', 'status', 'created_at'
    )
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = (
        'order__order_number', 'gateway_transaction_id',
        'shop_order__shop__name',
    )
    readonly_fields = (
        'order', 'shop_order', 'gateway', 'gateway_transaction_id',
        'amount', 'reason', 'created_by', 'created_at', 'updated_at',
    )

    actions = ['mark_processed', 'mark_declined']

    @admin.action(description="Mark selected refunds as processed")
    def mark_processed(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='processed', resolved_by=request.user
        )
        self.message_user(request, f"{updated} refunds marked as processed.")

    @admin.action(description="Mark selected refunds as declined")
    def mark_declined(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='declined', resolved_by=request.user
        )
        self.message_user(request, f"{updated} refunds marked as declined.")

    fieldsets = (
        ('Refund Information', {
            'fields': ('order', 'shop_order', 'gateway', 'gateway_transaction_id', 'amount', 'reason')
        }),
        ('Status', {
            'fields': ('status', 'created_by', 'resolved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
