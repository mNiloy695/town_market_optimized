from rest_framework import serializers


class VendorOrderStatsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivered_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    returned_orders = serializers.IntegerField()
    delivered_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivered_but_not_given_commission_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    need_to_pay_commission_to_the_platform = serializers.DecimalField(max_digits=12, decimal_places=2)
