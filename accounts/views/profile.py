from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes

from accounts.serializers import UserProfileSerializer
from accounts.models import UserProfile, CustomUser


class CustomProfilePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.user


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_view(request):
    try:
        profile = UserProfile.objects.select_related("user").get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    elif request.method == 'PATCH':
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "name",
            "phone",
            "country_code",
            "role",
            "is_request_for_shop",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method in ['PUT', 'PATCH']:
            if not request.user.is_superuser:
                # Sensitive fields that cannot be modified by staff
                sensitive_fields = ["role", "is_staff", "is_superuser", "is_active", "email", "phone"]
                for field in sensitive_fields:
                    if field in attrs:
                        if self.instance and getattr(self.instance, field) != attrs[field]:
                            raise serializers.ValidationError({field: f"Only superusers can modify the '{field}' field."})
                # Check if trying to modify a superuser
                if self.instance and self.instance.is_superuser:
                    raise serializers.ValidationError("Only superusers can modify superuser accounts.")
        return attrs


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, permissions.IsAdminUser])
def admin_users_list_view(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    serializer = AdminUserSerializer(users, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated, permissions.IsAdminUser])
def admin_user_detail_view(request, pk):
    try:
        user = CustomUser.objects.get(pk=pk)
    except CustomUser.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = AdminUserSerializer(user, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'PATCH':
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only superusers can modify user accounts."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = AdminUserSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
