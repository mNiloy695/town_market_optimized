from rest_framework import serializers
from cart.models import Cart


class CheckoutSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(max_length=2500)
    shipping_city = serializers.ChoiceField(choices=[('feni', 'Feni')])
    shipping_upazilla = serializers.ChoiceField(choices=[('feni_sadar', 'Feni Sadar'), ('parshuram', 'Parshuram'), ('chagalaiya', 'Chagalaiya'), ('daganbhuiyan', 'Daganbhuiyan'), ('sonagazi', 'Sonagazi'), ('fulgazi', 'Fulgazi')])
    shipping_postal_code = serializers.CharField(max_length=20)
    shipping_country = serializers.ChoiceField(choices=[('Bangladesh', 'Bangladesh')])
    phone_number = serializers.CharField(max_length=20)

    payment_method = serializers.ChoiceField(
        choices=['sslcommerz', 'bkash'],
        default='sslcommerz'
    )

    def validate_phone_number(self, value):
        import re
        pattern = r"^(?:\+88|88)?(01[3-9]\d{8})$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Please provide a valid Bangladeshi mobile number (e.g., 01712345678).")
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required")

        shipping_address = data.get('shipping_address', None)
        shipping_city = data.get('shipping_city', None)
        shipping_postal_code = data.get('shipping_postal_code', None)
        shipping_country = data.get('shipping_country', None)
        shipping_upazilla = data.get('shipping_upazilla', None)
        phone_number = data.get('phone_number', None)
        if not (shipping_address and shipping_city and shipping_country and shipping_postal_code and phone_number and shipping_upazilla):
            raise serializers.ValidationError({"error": "shipping address, city, postal code,shipping_upazilla, country and phone number are required"})

        try:
            cart = Cart.objects.get(user=request.user)
            if not cart.items.exists():
                raise serializers.ValidationError("Cart is empty")
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found")

        return data

    def create(self, validated_data):
        raise NotImplementedError(
            "Use CheckoutView.perform_checkout() instead of serializer.save()"
        )
