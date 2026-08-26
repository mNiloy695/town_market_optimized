from rest_framework import serializers
from shop.models import Category, Shop


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ShopSerializer(serializers.ModelSerializer):
    market_data = serializers.SerializerMethodField(read_only=True)
    category_data = CategorySerializer(source='Category', many=True, read_only=True)
    latitude = serializers.DecimalField(max_digits=20, decimal_places=15, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=20, decimal_places=15, required=False, allow_null=True)

    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ('owner', 'created_at', 'updated_at', 'category_data', 'market_data')

    def validate_latitude(self, value):
        if value is not None:
            return round(value, 6)
        return value

    def validate_longitude(self, value):
        if value is not None:
            return round(value, 6)
        return value

    def validate(self, data):
        request = self.context.get('request')
        if request and request.method in ['PATCH', 'PUT']:
            user = request.user
            if not user.is_staff:
                for field in ('status', 'is_active', 'is_deactivated'):
                    if field in data:
                        raise serializers.ValidationError(
                            {field: "Only admin can modify this field."}
                        )
        return data

    def validate_market(self, value):
        request = self.context.get('request')
        if request and request.method in ['PATCH', 'PUT']:
            user = request.user
            if not user.is_superuser:
                old_market = self.instance.market if self.instance else None
                if old_market and old_market != value:
                    raise serializers.ValidationError(
                        "You cannot directly update the market. Contact admin."
                    )
        return value

    def get_market_data(self, obj):
        return {
            "id": obj.market.id,
            "name": obj.market.name,
            "slug": obj.market.slug,
        }
