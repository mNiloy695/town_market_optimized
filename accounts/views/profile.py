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


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, permissions.IsAdminUser])
def admin_users_list_view(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    serializer = AdminUserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated, permissions.IsAdminUser])
def admin_user_detail_view(request, pk):
    try:
        user = CustomUser.objects.get(pk=pk)
    except CustomUser.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = AdminUserSerializer(user)
        return Response(serializer.data)

    elif request.method == 'PATCH':
        serializer = AdminUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
