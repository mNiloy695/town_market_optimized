from rest_framework import serializers
from order.models import ShopOrder


class ShopOrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopOrder
        fields = ['status', 'tracking_number', 'notes']

    def validate(self, data):
        instance = self.instance
        value = data.get('status')

        if not value:
            return data

        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['processing', 'cancelled'],
            'processing': ['shipped', 'cancelled'],
            'shipped': ['delivered'],
            'delivered': ['return_requested', 'returned'],
            'cancelled': [],
            'return_requested': ['returned'],
            'returned': [],
        }

        if instance and instance.status in valid_transitions:
            if value not in valid_transitions[instance.status]:
                from rest_framework.exceptions import APIException
                from rest_framework import status as http_status

                class BadRequest(APIException):
                    status_code = http_status.HTTP_400_BAD_REQUEST

                raise BadRequest(
                    {"error": f"Invalid status transition from {instance.status} to {value}"}
                )

        return data
