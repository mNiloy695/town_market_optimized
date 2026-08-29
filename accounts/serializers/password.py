from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password


class ChangingPassword(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        current_password = attrs.get('current_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        user = self.context['request'].user

        if not current_password:
            raise serializers.ValidationError({"error": "Current Password field is required."})

        if not new_password:
            raise serializers.ValidationError({"error": "New password field cannot be null."})

        if not confirm_password:
            raise serializers.ValidationError({"error": "Confirm password field cannot be null."})

        if new_password != confirm_password:
            raise serializers.ValidationError({"error": "New password and confirm password do not match."})

        if not user.check_password(current_password):
            raise serializers.ValidationError({"error": "Your current password is incorrect."})

        try:
            validate_password(new_password, user=user)
        except Exception as e:
            raise serializers.ValidationError({"error": list(e.messages)})

        return attrs
