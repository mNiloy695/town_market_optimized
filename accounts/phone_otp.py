from django.conf import settings
from twilio.rest import Client

def otp_send(phone,otp_code,main_message):
    try:
        client=Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
                )
        message=client.messages.create(
                body=f"Here your one time OTP {otp_code} for {main_message}.Don't share it to anyone !.It will expire within 3 min",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone
            )
        print("top sended")
        return f"OTP  Sucessfully send to {phone} check your SMS box"
    
    except Exception as e:
        print("error is occure")
        return f"A error is occure during sending otp {e}" 
    

        
