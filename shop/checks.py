from rest_framework import serializers


def validate_user_active(user):
    if not user.is_active:
        raise serializers.ValidationError({"detail": "Your account has been deactivated."})


def validate_shop_active(shop):
    if not shop.is_active:
        raise serializers.ValidationError({"detail": "Your shop has been suspended. Please contact support."})
    if shop.is_deactivated:
        raise serializers.ValidationError({"detail": "Your shop has been deactivated. Please contact support."})
    if shop.status != 'approved':
        raise serializers.ValidationError({"detail": f"Your shop is currently {shop.status}. It must be approved to perform this action."})


def get_vendor_shop(user):
    if user.role != 'seller':
        raise serializers.ValidationError({"detail": "Only sellers can perform this action."})
    if not user.is_active:
        raise serializers.ValidationError({"detail": "Your account has been deactivated."})
    from shop.models import Shop
    shop = Shop.objects.filter(owner=user).first()
    if not shop:
        raise serializers.ValidationError({"detail": "You do not have a shop registered."})
    validate_shop_active(shop)
    return shop
