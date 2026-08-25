import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SMS_API_URL = "https://sms.corp.com.bd/api.php"

def otp_send(phone, otp_code, main_message):
    try:
        message = f"Here your one time OTP {otp_code} for {main_message}. Don't share it to anyone! It will expire within 3 min"
        numbers = phone
        
        params = {
            "api_key": settings.SMS_API_KEY,
            "action": "send_sms",
            "numbers": numbers,
            "message": message,
            "sender_id": "8809617635077"
        }
        
        response = requests.get(SMS_API_URL, params=params)
        response.raise_for_status()
        
        logger.info("OTP sent to %s via Bangladeshi SMS service", phone)
        return f"OTP Successfully sent to {phone} check your SMS box"
    
    except Exception as e:
        logger.error("Error sending OTP: %s", e)
        return f"A error occurred during sending otp: {e}" 
    

        
