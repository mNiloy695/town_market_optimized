from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.serializers import RegistrationSerializer, LoginSerializer
from accounts.models import OTP
from accounts.task import phone_otp_send
from rest_framework_simplejwt.tokens import RefreshToken


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            user.is_active = False
            user.save()
            otp_code = OTP.generate_code()

            try:
                OTP.objects.create(
                    user=user,
                    code=otp_code,
                    type="active"
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error("Failed to create OTP for user %s: %s", user.id, e)
                return Response(
                    {"error": "Failed to send OTP. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            phone_otp_send.delay(phone=str(user.phone), otp=otp_code, main_message="active you 'Town Market' account")

            return Response({
                "message": "OTP sent successfully! Check your SMS inbox.",
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "User login sucessfully",
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "phone": user.phone,
                        "is_request_for_shop": user.is_request_for_shop,
                    },
                    "refresh": str(refresh),
                    "access": str(refresh.access_token)
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh", None)
            if not refresh_token:
                return Response(
                    {"error": "Refresh token not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                "message": "Logout successful"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": "Invalid token"
            }, status=status.HTTP_400_BAD_REQUEST)


# The OTP / password views live in accounts.views.otp.
# These re-exports keep any `from .auth import ...` imports working and
# prevent duplicated, drifting OTP logic.
from .otp import (
    ActiveUserAccountView, ForgotPasswordandResendView,
    VerifyOTPView, ResetPasswordView, ChangePasswordView,
)