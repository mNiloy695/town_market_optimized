from rest_framework import serializers
from .models import Shop,Category,RequestForShop


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model=Category
        fields='__all__'

class ShopSerializer(serializers.ModelSerializer):
    market_data=serializers.SerializerMethodField(read_only=True)
    category_data = CategorySerializer(source='Category', many=True, read_only=True)
    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ('owner','created_at','updated_at','status','category_data','market_data')

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
    
    def get_market_data(self,obj):
        return {
            "id":obj.market.id,
            "name":obj.market.name,
            "slug":obj.market.slug
        }
    
   

class RequestForShopSerializer(serializers.ModelSerializer):
    shop_data = ShopSerializer(write_only=True)
    shop = ShopSerializer(read_only=True)

    class Meta:
        model = RequestForShop
        fields = ['id', 'user', 'shop', 'created_at', 'updated_at', 'status', 'shop_data']
        read_only_fields = ('user', 'shop', 'created_at', 'updated_at', 'status')

    def validate(self, attrs):
        user = self.context['request'].user
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
     
       
        request_obj = RequestForShop.objects.create(
            user=user,
            shop=shop,
            **validated_data
        )
        
        return request_obj

from .models import Market

class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model=Market
        fields="__all__"
    
    