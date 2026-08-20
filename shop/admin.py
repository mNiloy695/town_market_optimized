from django.contrib import admin
from django.db.models import Sum
from .models import Category, Market, Shop, RequestForShop

# Register your models here.
admin.site.register(Category)
admin.site.register(Market)
admin.site.register(RequestForShop)

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'market', 'status', 'outstanding_commission')
    list_filter = ('status', 'market')
    search_fields = ('name', 'owner__name', 'owner__phone')
    
    actions = ['settle_all_commissions']
    
    def outstanding_commission(self, obj):
        """Displays total outstanding commission for this shop"""
        from order.models import ShopOrder
        from core.settings import COMMISSION_PERCENTAGE
        
        # Calculate sum of delivered orders without commission paid
        total_delivered = ShopOrder.objects.filter(
            shop=obj, 
            status='delivered', 
            commission_given=False
        ).aggregate(Sum('total'))['total__sum'] or 0
        
        amount = total_delivered * COMMISSION_PERCENTAGE
        return f"₨ {amount:,.2f}"
    outstanding_commission.short_description = "Pending Commission"

    @admin.action(description="Settle all outstanding commissions for selected shops")
    def settle_all_commissions(self, request, queryset):
        """Marks all delivered orders for the selected shops as commission paid"""
        from order.models import ShopOrder
        total_settled_orders = 0
        
        for shop in queryset:
            unpaid_orders = ShopOrder.objects.filter(
                shop=shop, 
                status='delivered', 
                commission_given=False
            )
            count = unpaid_orders.update(commission_given=True)
            total_settled_orders += count
            
        self.message_user(
            request, 
            f"Successfully settled commissions for {queryset.count()} shops (updated {total_settled_orders} orders)."
        )