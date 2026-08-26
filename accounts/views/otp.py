from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from random import randint

from accounts.models import OTP
from accounts.validate_number import validated_phone_number
from accounts.task import phone_otp_send
from django.contrib.auth import get_user_model

User = get_user_model()


class ActiveUserAccountView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", None)
        code = request.data.get("code", None)
        country_code = request.data.get("country_code", None)

        if not phone or not code or not country_code:
            return Response(
                {"error": "phone ,code, type , country_code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = validated_phone_number(phone=phone, country_code=country_code)
        if isinstance(result, dict) and "error" in result:
            return Response(result, status=400)

        phone = result.as_e164
        otp = OTP.objects.select_related('user').filter(
            user__phone=phone,
            type="active"
        ).first()

        if not otp:
            return Response(
                {"error": "OTP is invalid"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.is_locked():
            return Response(
                {"error": "Too many failed attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if otp.is_expired():
            return Response(
                {"error": "OTP is expired"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.code != code:
            otp.record_failed_attempt()
            return Response(
                {"error": "OTP is invalid"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = otp.user
        if user.is_verified:
            return Response(
                {"error": "Account was previously deactivated by admin. Please contact support."},
                status=status.HTTP_403_FORBIDDEN
            )
        user.is_active = True
        user.is_verified = True
        user.save(update_fields=['is_active', 'is_verified'])

        otp.delete()

        return Response({"message": "User activated successfully"}, status=status.HTTP_200_OK)


class ForgotPasswordandResendView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", None)
        country_code = request.data.get("country_code", None)
        action = request.data.get("action", None)
        if not phone or not country_code or not action:
            return Response({"error": "phone, country_code , action fields are required !"}, status=status.HTTP_400_BAD_REQUEST)

        if action not in ["reset", "active"]:
            return Response({"error": "action only be reset or active"}, status=status.HTTP_400_BAD_REQUEST)

        result = validated_phone_number(phone=phone, country_code=country_code)

        if isinstance(result, dict) and "error" in result:
            return Response(result, status=400)

        try:
            phone = result.as_e164
            user = User.objects.prefetch_related("otps").get(phone=phone)
        except User.DoesNotExist:
            return Response({"message": "If an account with this phone exists, an OTP has been sent."})

        if action == "reset":
            existing_otp = user.otps.filter(type="reset").first()
        elif action == "active":
            if user.is_active and user.is_verified:
                return Response({"message": "If an account with this phone exists, an OTP has been sent."})
            existing_otp = user.otps.filter(type="active").first()
        else:
            existing_otp = None

        if existing_otp and not existing_otp.is_expired():
            return Response({"message": "you can resend request for otp after 3 min"}, status=status.HTTP_400_BAD_REQUEST)

        code = randint(1000, 9999)

        if action == "reset":
            OTP.objects.create(
                user=user,
                code=code,
                type="reset"
            )
            phone_otp_send.delay(phone=phone, otp=code, main_message="reset password of Town Market")

        elif action == "active":
            OTP.objects.create(
                user=user,
                code=code,
                type="active"
            )
            phone_otp_send.delay(phone=phone, otp=code, main_message="active Town Market")

        return Response(
            {
                "message": f"OTP  Sucessfully send to {phone} check your SMS box",
            }, status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", None)
        country_code = request.data.get("country_code", None)
        code = request.data.get("code", None)

        if not phone or not country_code or not code:
            return Response({"error": "phone, country_code, code, and action fields are required!"}, status=status.HTTP_400_BAD_REQUEST)

        result = validated_phone_number(phone=phone, country_code=country_code)
        if isinstance(result, dict) and "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        phone = result.as_e164

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"error": "Invalid user"}, status=status.HTTP_400_BAD_REQUEST)

        otp = user.otps.filter(type='reset').first()

        if not otp:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_locked():
            return Response(
                {"error": "Too many failed attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if otp.is_expired():
            return Response({"error": "OTP is expired"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.code != code:
            otp.record_failed_attempt()
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        otp.reset_failed_attempts()

        return Response({"message": "OTP verified successfully"}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        phone = data.get("phone", None)
        country_code = data.get("country_code", None)
        password = data.get("password", None)
        confirm_password = data.get("confirm_password", None)
        code = data.get("code", None)

        if not phone or not password or not confirm_password or not country_code or not code:
            return Response({"error": "phone,password,confirm_password, country_code, code fields are required"}, status=status.HTTP_400_BAD_REQUEST)

        if password != confirm_password:
            return Response({"error": "password and confirm password not matched"}, status=status.HTTP_400_BAD_REQUEST)

        result = validated_phone_number(phone=phone, country_code=country_code)

        if isinstance(result, dict) and "error" in result:
            return Response(result, status=400)

        phone = result.as_e164

        try:
            user = User.objects.prefetch_related("otps").get(phone=phone)
        except User.DoesNotExist:
            return Response({"error": "Invalid User"}, status=status.HTTP_400_BAD_REQUEST)

        otp = user.otps.filter(type="reset").first()

        if not otp:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_locked():
            return Response(
                {"error": "Too many failed attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if otp.is_expired():
            return Response({"error": "Otp is expired"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.code != code:
            otp.record_failed_attempt()
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=['password'])
        otp.delete()

        return Response({
            "message": "Password reset sucessfully",
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response(
                {"error": "Your account has been deactivated"},
                status=status.HTTP_403_FORBIDDEN
            )
        from accounts.serializers import ChangingPassword
        serializer = ChangingPassword(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            password = serializer.validated_data['new_password']
            user.set_password(password)
            user.save()
            return Response({"message": "your password succesfully changed"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)