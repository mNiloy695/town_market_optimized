from rest_framework import serializers
from shop.models import Category, Shop


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ShopSerializer(serializers.ModelSerializer):
    market_data = serializers.SerializerMethodField(read_only=True)
    category_data = CategorySerializer(source='Category', many=True, read_only=True)

    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ('owner', 'created_at', 'updated_at', 'status', 'category_data', 'market_data')

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
