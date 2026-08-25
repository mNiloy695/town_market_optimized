from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import NumberParseException

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email',
            'name',
            'phone',
            'country_code',
            'role',
            'birth_date',
            'password',
            'confirm_password',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True},
        }

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        phone = attrs.get('phone')
        country_code = attrs.get('country_code')

        if not password or not confirm_password:
            raise serializers.ValidationError({"error": "Password and confirm password are required"})

        if password != confirm_password:
            raise serializers.ValidationError({"error": "Passwords do not match"})

        try:
            validate_password(password)
        except Exception as e:
            raise serializers.ValidationError({"error": list(e.messages)})
        try:
            phone_number = PhoneNumber.from_string(phone, region=country_code)
            if not phone_number.is_valid():
                raise serializers.ValidationError({"error": "Invalid phone number"})

            if User.objects.filter(phone=phone_number).exists():
                raise serializers.ValidationError({"error": "An account with this phone or email already exists"})

        except NumberParseException:
            raise serializers.ValidationError({"error": "Invalid phone number or country code"})

        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    country_code = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone", None)
        password = attrs.get("password", None)
        country_code = attrs.get("country_code", None)

        if not phone:
            raise serializers.ValidationError({"error": "Phone number must be required"})

        GENERIC_LOGIN_ERROR = {"error": "Invalid phone number or password"}

        try:
            phone_number = PhoneNumber.from_string(
                phone,
                region=country_code
            )

            if not phone_number.is_valid():
                raise serializers.ValidationError({"error": "Invalid Phone Number Format"})

            try:
                user = User.objects.get(phone=phone_number)
            except User.DoesNotExist:
                raise serializers.ValidationError(GENERIC_LOGIN_ERROR)

        except NumberParseException:
            raise serializers.ValidationError({"error": "Invalid phone number or country code"})

        if not user.is_active:
            raise serializers.ValidationError(GENERIC_LOGIN_ERROR)

        if not user.check_password(password):
            raise serializers.ValidationError(GENERIC_LOGIN_ERROR)

        attrs['user'] = user
        return attrs
