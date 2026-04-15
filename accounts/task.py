from celery import shared_task
from .phone_otp import otp_send
@shared_task
def phone_otp_send(phone,otp,main_message="active your Town Market account"):
    #otp send import from phone_otp.py modul/file
    message=otp_send(phone=phone,otp_code=otp,main_message=main_message)
    return message
    