from rest_framework import serializers
from shop.models import RequestForShop, Shop
from .shop import CategorySerializer


class ShopWriteSerializer(serializers.ModelSerializer):
    category_data = CategorySerializer(source='Category', many=True, read_only=True)
    latitude = serializers.DecimalField(max_digits=20, decimal_places=15, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=20, decimal_places=15, required=False, allow_null=True)

    class Meta:
        model = Shop
        fields = ['name', 'description', 'phone', 'logo', 'cover_image', 'address',
                  'market', 'Category', 'opening_time', 'closing_time',
                  'longitude', 'latitude', 'category_data']
        read_only_fields = ['category_data']

    def validate_latitude(self, value):
        if value is not None:
            return round(value, 6)
        return value

    def validate_longitude(self, value):
        if value is not None:
            return round(value, 6)
        return value


class RequestForShopSerializer(serializers.ModelSerializer):
    shop_data = ShopWriteSerializer(write_only=True)
    shop = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RequestForShop
        fields = ['id', 'user', 'shop', 'created_at', 'updated_at', 'status', 'shop_data']
        read_only_fields = ('user', 'shop', 'created_at', 'updated_at')

    def get_shop(self, obj):
        from .shop import ShopSerializer
        return ShopSerializer(obj.shop).data

    def validate_status(self, value):
        request = self.context.get('request')
        if request and not request.user.is_staff:
            if value != 'pending':
                raise serializers.ValidationError("Only staff members can set or change the status of a shop request.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            return attrs
        user = self.context['request'].user
        if not user.is_active:
            raise serializers.ValidationError({"error": "Your account has been deactivated."})
        if Shop.objects.filter(owner=user).exists():
            shop = Shop.objects.get(owner=user)
            raise serializers.ValidationError({
                "error": f"You already have a shop or a request (Status: {shop.status}). Please contact admin."
            })
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        shop_data = validated_data.pop('shop_data')
        categories = shop_data.pop('Category', [])
        shop = Shop.objects.create(owner=user, **shop_data)
        if categories:
            shop.Category.set(categories)
        if not user.is_staff:
            validated_data['status'] = 'pending'
        request_obj = RequestForShop.objects.create(
            user=user,
            shop=shop,
            **validated_data
        )
        return request_obj
