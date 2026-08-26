from .auth import RegistrationView, LoginView, LogoutView
from .profile import user_profile_view, CustomProfilePermission, admin_users_list_view, admin_user_detail_view
from .otp import (
    ActiveUserAccountView, ForgotPasswordandResendView,
    VerifyOTPView, ResetPasswordView, ChangePasswordView
)
from .token import refresh_token_view

__all__ = [
    'RegistrationView',
    'LoginView',
    'LogoutView',
    'user_profile_view',
    'CustomProfilePermission',
    'ActiveUserAccountView',
    'ForgotPasswordandResendView',
    'VerifyOTPView',
    'ResetPasswordView',
    'ChangePasswordView',
    'refresh_token_view',
    'admin_users_list_view',
    'admin_user_detail_view',
]
