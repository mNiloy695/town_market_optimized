from celery import shared_task
from .phone_otp import otp_send
@shared_task
def phone_otp_send(phone,otp,main_message="active your Town Market account"):
    #otp send import from phone_otp.py modul/file
    message=otp_send(phone=phone,otp_code=otp,main_message=main_message)
    return message


@shared_task
def cleanup_unverified_users():
    from django.utils import timezone
    from accounts.models import CustomUser

    # Delete users who registered but haven't verified (is_verified=False) after 15 minutes
    expiry_time = timezone.now() - timezone.timedelta(minutes=15)
    unverified_users = CustomUser.objects.filter(
        is_verified=False,
        is_staff=False,
        is_superuser=False,
        date_joined__lt=expiry_time
    )
    deleted_count, deleted_details = unverified_users.delete()
    user_deleted_count = deleted_details.get('accounts.CustomUser', 0)
    return f"Deleted {user_deleted_count} unverified users."
    