from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import NumberParseException


def validated_phone_number(phone,country_code):
      try:
            phone_number=PhoneNumber.from_string(
                phone,
                region=country_code
            )
            
            if not phone_number.is_valid():
                return  {"error":"Invalid Phone Number Format"}
            
            
      except NumberParseException:
             
            return {"error":"Invalid phone number or country code"}
        
      return phone_number