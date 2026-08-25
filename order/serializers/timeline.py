from rest_framework import serializers
from order.models import OrderTimeline


class OrderTimelineSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = OrderTimeline
        fields = ['id', 'action', 'description', 'created_at', 'user_name']
        read_only_fields = ['id', 'created_at']
