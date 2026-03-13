from django.shortcuts import render
from django.db.models import Q
from rest_framework import generics
from .serializers import RegistrationSerializer,LoginSerializer
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status
from .models import OTP
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt import token_blacklist
from random import randint
from twilio.rest import Client
from django.conf import settings
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import NumberParseException
# from .phone_otp import otp_send
from .task import phone_otp_send
from .validate_number import validated_phone_number
from django.contrib.auth import get_user_model
User=get_user_model()
class ResgistrationView(APIView):
    def post(self,request):
        serializer=RegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user=serializer.save()
            user.is_active=False
            user.save()
            otp_code=randint(1000,9999)
            
            try:
                OTP.objects.create(
                user=user,
                code=otp_code,
                type="active"
            )
                
            except Exception as e:
                print("otp not crate a problem ",{e})
                
            
            print("Here is your otp",otp_code)
            
            #phone_otp_send running in backgroud and it's imported from task.py
            
            message=phone_otp_send.delay(phone=str(user.phone),otp=otp_code,main_message="active you 'Town Market' account")
            
            
            return Response({
                "message": "OTP sent successfully! Check your SMS inbox.",
                "otp":otp_code
                
            },status=status.HTTP_200_OK)
        
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
            
      
class LoginView(APIView):
    def post(self,request):
        serializer=LoginSerializer(data=request.data)
        if serializer.is_valid():
            user=serializer.validated_data["user"]
            
            refresh=RefreshToken.for_user(user)
            
            return Response(
                {
                    "message":"User login sucessfully",
                     "user":{
                         "id":user.id,
                         "name":user.name,
                         "phone":user.phone,
                         "email":user.email,
                         "birth_date":user.birth_date,
                         "is_request_for_shop":user.is_request_for_shop,
                     },
                     
                     "refresh":str(refresh),
                     "access":str(refresh.access_token)
                }
            )
        
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
    
from .serializers import UserProfileSerializer
from .models import UserProfile

class CustomProfilePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user==obj.user



from rest_framework.decorators import api_view, permission_classes

@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_view(request):
    try:
        profile = UserProfile.objects.select_related("user").get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    
    elif request.method == 'PATCH':
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


#Logout View

class LogoutView(APIView):
    def post(self,request):
        try:
            refresh_token=request.data.get("refresh",None)
            if not refresh_token:
                return Response(
                    {"error":"Refresh token not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token=RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                "message":"Logout successful"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error":"Invalid token"
            }, status=status.HTTP_400_BAD_REQUEST)
            
            

from django.utils import timezone

class ActiveUserAccountView(APIView):
    def post(self, request):
        phone = request.data.get("phone",None)
        code = request.data.get("code",None)
        country_code=request.data.get("country_code",None)
        
        if not phone or not code  or not country_code:
            
            return Response(
                {"error":"phone ,code, type , country_code is required"},
            )
            

        result=validated_phone_number(phone=phone,country_code=country_code)
        if isinstance(result, dict) and "error" in result:
            return Response(result, status=400)

        phone=result.as_e164
        otp = OTP.objects.select_related('user').filter(
            user__phone=phone,
            code=code,
            type="active"
        ).first()
        
        print(otp)
      
        if not otp:
            return Response(
                {"error": "OTP is invalid"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.is_expired():
            
            return Response(
                {"error": "OTP is expired"},
                status=status.HTTP_400_BAD_REQUEST
            ) 
        
        
        user = otp.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        
        otp.delete()

        return Response({"message": "User activated successfully"}, status=status.HTTP_200_OK)
    
    
    
    

#forgot password

class ForgotPasswordandResendView(APIView):
    def post(self,request):
        phone = request.data.get("phone",None)
        country_code=request.data.get("country_code",None)
        action=request.data.get("action",None)
        if not phone or not country_code or not action:
            return Response({"error":"phone, country_code , action fields are required !"})
        
    
        
        if action not in ["reset","active"]:
            return Response({"error":"action only be reset or active"},status=status.HTTP_400_BAD_REQUEST)
        
        result=validated_phone_number(phone=phone,country_code=country_code)
        
        if isinstance(result, dict) and "error" in result:
            return Response(result, status=400)

        
        try:
            phone=result.as_e164
          
            user=User.objects.prefetch_related("otps").get(phone=phone)
            
        except User.DoesNotExist:
            return Response({"error":"Invalid user"})
        
        if action=="reset":
            existing_otp = user.otps.filter(type="reset").first()
            
        if action=="active":
            existing_otp = user.otps.filter(type="active").first()
    

        if existing_otp and not existing_otp.is_expired():
          
            
            return Response({"message":"you can resend request for otp after 3 min"},status=status.HTTP_400_BAD_REQUEST)
        
        code=randint(1000,9999)
        
        
        if action=="reset":
            OTP.objects.create(
            user=user,
            code=code,
            type="reset"
            
        )
        phone_otp_send.delay(phone=phone,otp=code,main_message="reset password of Town Market")
        
        if action=="active":
              OTP.objects.create(
            user=user,
            code=code,
            type="active"
            
        )
        phone_otp_send.delay(phone=phone,otp=code,main_message="active Town Market")
        
       
      
        return Response(
            {
                "message":f"OTP  Sucessfully send to {phone} check your SMS box",
                "otp":code
            },status=status.HTTP_200_OK
        )
        
        
        
from datetime import timedelta
class VerifyOTPView(APIView):
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

        

        otp = user.otps.filter(code=code, type='reset').first()

        if not otp:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_expired():
            return Response({"error": "OTP is expired"}, status=status.HTTP_400_BAD_REQUEST)

        otp.created_at=timezone.now()+timedelta(minutes=5)
        otp.save()

        

        return Response({"message": "OTP verified successfully"}, status=status.HTTP_200_OK)


#reset password

class ResetPasswordView(APIView):
    def post(self,request):
        data=request.data 
        
        phone=data.get("phone",None)
        country_code=data.get("country_code",None)
        password=data.get("password",None)
        confirm_password=data.get("confirm_password",None)
        code=data.get("code",None)
        
        if not phone or not password or not confirm_password  or not country_code or not code:
            return Response({"error":"phone,password,confirm_password, country_code, code fields are required"},status=status.HTTP_400_BAD_REQUEST)
        
        
        if password != confirm_password:
            return Response({"error":"password and confirm password not matched"},status=status.HTTP_400_BAD_REQUEST)
        
        result=validated_phone_number(phone=phone,country_code=country_code)
        
        if isinstance(result,dict) and "error" in result:
            return Response(result,status=400)
        
        phone=result.as_e164
        
        try:
            user=User.objects.prefetch_related("otps").get(phone=phone)
        except User.DoesNotExist:
            return Response({"error":"Invalid User"},status=status.HTTP_400_BAD_REQUEST)
        
        otp=user.otps.filter(code=code,type="reset").first()
        
        if not otp:
            return Response({"error":"Invalid OTP"},status=status.HTTP_400_BAD_REQUEST)
        
        if otp.is_expired():
            return Response({"error":"Otp is expired"},status=status.HTTP_400_BAD_REQUEST)
        
        if user.is_active==False:
            user.is_active=True
            user.save()
        
        user.set_password(password)
        user.save()
        otp.delete()
        
        return Response({
            "message":"Password reset sucessfully",
        },status=status.HTTP_200_OK)
        
        

from .serializers import ChangingPassword


class ChangePasswordView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    def post(self,request):
         serializer = ChangingPassword(data=request.data, context={'request': request})
         if serializer.is_valid():
             user=request.user
             password=serializer.validated_data['new_password']
             user.set_password(password)
             user.save()
             return Response({"message":"your password succesfully changed"},status=status.HTTP_200_OK)
         
         return Response(serializer.errors)
        
        
        
        
        
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


User = get_user_model()

@api_view(['POST'])
def refresh_token_view(request):
    try:
        old_refresh = request.data["refresh"]

        old_token = RefreshToken(old_refresh)

        user_id = old_token["user_id"]

        user = User.objects.get(pk=user_id)

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