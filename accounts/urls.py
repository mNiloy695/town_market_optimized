from django.urls import path,include
from .views import RegistrationView,LoginView,LogoutView,ActiveUserAccountView,ForgotPasswordandResendView,ResetPasswordView,VerifyOTPView,user_profile_view,refresh_token_view
from rest_framework.routers import DefaultRouter
from .views import ChangePasswordView

from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

urlpatterns = [
    path('auth/registration/',RegistrationView.as_view(),name="register"),
    path("auth/login/",LoginView.as_view(),name='login'),
    path("auth/logout/",LogoutView.as_view(),name='logout'),
    path("auth/active/",ActiveUserAccountView.as_view(),name="active"),
    path("auth/forgot-password/",ForgotPasswordandResendView.as_view(),name="forgot-password"),
    path("auth/resend-otp-for-account-active/",ForgotPasswordandResendView.as_view(),name="resend-otp"),
    path("auth/verify-otp/",VerifyOTPView.as_view(),name="verify-otp"),
    path("auth/reset-password/",ResetPasswordView.as_view(),name="reset-password"),
    path("auth/password-change/",ChangePasswordView.as_view(),name='password-change'),
    path('auth/profile/',user_profile_view,name='profile'),
    path("auth/token/refresh/",refresh_token_view, name='token_refresh'),
]


