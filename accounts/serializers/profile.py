from rest_framework import serializers
from accounts.models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField(read_only=True)
    is_request_for_shop = serializers.SerializerMethodField(read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    is_staff = serializers.BooleanField(source="user.is_staff", read_only=True)
    is_superuser = serializers.BooleanField(source="user.is_superuser", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "user", "avatar", "name", "email", "gender", "birth_date", "phone", "is_request_for_shop", "role", "is_staff", "is_superuser"]
        read_only_fields = ['user', 'id']

    def get_phone(self, instance):
        if hasattr(instance.user, "phone"):
            return str(instance.user.phone)
        return None

    def get_is_request_for_shop(self, instance):
        if getattr(instance.user, 'is_request_for_shop'):
            return str(instance.user.is_request_for_shop)
        return None
