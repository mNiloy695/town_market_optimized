from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(['POST'])
def refresh_token_view(request):
    try:
        old_refresh = request.data["refresh"]

        old_token = RefreshToken(old_refresh)

        user_id = old_token["user_id"]

        user = User.objects.get(pk=user_id)

        if not user.is_active:
            return Response(
                {"error": "Your account has been deactivated"},
                status=status.HTTP_403_FORBIDDEN
            )

        old_token.blacklist()

        new_refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(new_refresh),
            "access": str(new_refresh.access_token),
        })

    except (TokenError, User.DoesNotExist):
        return Response(
            {"error": "Invalid or expired token"},
            status=status.HTTP_400_BAD_REQUEST
        )
