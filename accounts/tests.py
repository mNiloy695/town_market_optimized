from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import OTP, UserProfile
from accounts.task import cleanup_unverified_users

User = get_user_model()

class AccountsAPITests(APITestCase):
    def setUp(self):
        pass

    @patch('accounts.views.auth.phone_otp_send.delay')
    def test_user_registration_flow_success(self, mock_otp_send):
        """Test successful registration of a user"""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "01806779331",
            "country_code": "BD",
            "birth_date": "2000-01-01",
            "role": "buyer",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/registration/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(phone="+8801806779331").exists())
        
        user = User.objects.get(phone="+8801806779331")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_verified)
        
        # Verify Profile was created by signal
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        
        # Verify OTP was created
        self.assertTrue(OTP.objects.filter(user=user, type="active").exists())
        mock_otp_send.assert_called_once()

    def test_registration_mismatched_passwords(self):
        """Test registration failure when password and confirm_password do not match"""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "01806779331",
            "country_code": "BD",
            "birth_date": "2000-01-01",
            "role": "buyer",
            "password": "SecurePassword123",
            "confirm_password": "DifferentPassword123"
        }
        response = self.client.post('/v1/accounts/auth/registration/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_registration_duplicate_phone(self):
        """Test registration failure for duplicate phone number"""
        User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Existing User"
        )
        data = {
            "name": "New User",
            "email": "new@example.com",
            "phone": "01806779331",
            "country_code": "BD",
            "birth_date": "2000-01-01",
            "role": "buyer",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/registration/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_registration_invalid_phone(self):
        """Test registration failure for invalid phone number"""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "12345",  # Invalid number
            "country_code": "BD",
            "birth_date": "2000-01-01",
            "role": "buyer",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/registration/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_activation_success(self):
        """Test successful activation via valid OTP"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        otp = OTP.objects.create(user=user, code="1234", type="active")
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "1234"
        }
        response = self.client.post('/v1/accounts/auth/active/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_verified)
        self.assertFalse(OTP.objects.filter(id=otp.id).exists())

    def test_user_activation_invalid_otp(self):
        """Test activation fails with invalid OTP"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        OTP.objects.create(user=user, code="1234", type="active")
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "9999"
        }
        response = self.client.post('/v1/accounts/auth/active/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_verified)

    def test_user_activation_expired_otp(self):
        """Test activation fails with expired OTP"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        otp = OTP.objects.create(user=user, code="1234", type="active")
        # Force set created_at to past to expire it
        otp.created_at = timezone.now() - timezone.timedelta(minutes=10)
        otp.save()
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "1234"
        }
        response = self.client.post('/v1/accounts/auth/active/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data.get("error", "").lower())

    def test_otp_brute_force_lockout(self):
        """Test account gets locked after multiple failed attempts"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        otp = OTP.objects.create(user=user, code="1234", type="active")
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "9999"
        }
        
        # Make 5 failed attempts
        for _ in range(5):
            response = self.client.post('/v1/accounts/auth/active/', data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            
        # 6th attempt should be locked out
        response = self.client.post('/v1/accounts/auth/active/', data)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_success(self):
        """Test successful login of an active user"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=True
        )
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "password": "SecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/login/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_inactive_user_fails(self):
        """Test login fails for an inactive/unverified user"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "password": "SecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/login/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('accounts.views.auth.phone_otp_send.delay')
    def test_forgot_password_and_resend_otp(self, mock_otp_send):
        """Test forgot password request creates reset OTP and resend creates active OTP"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=True
        )
        
        # Forgot password reset request
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "action": "reset"
        }
        response = self.client.post('/v1/accounts/auth/forgot-password/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(OTP.objects.filter(user=user, type="reset").exists())
        mock_otp_send.assert_called_once()
        mock_otp_send.reset_mock()
        
        # Resend active OTP request (requires user is_active=False to resend active)
        user.is_active = False
        user.save()
        
        # Clear existing OTPs
        user.otps.all().delete()
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "action": "active"
        }
        response = self.client.post('/v1/accounts/auth/resend-otp-for-account-active/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(OTP.objects.filter(user=user, type="active").exists())
        mock_otp_send.assert_called_once()

    def test_verify_otp_for_reset_success(self):
        """Test verifying reset OTP successfully"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=True
        )
        OTP.objects.create(user=user, code="5678", type="reset")
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "5678"
        }
        response = self.client.post('/v1/accounts/auth/verify-otp/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reset_password_success(self):
        """Test password reset successfully with valid OTP"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=False
        )
        OTP.objects.create(user=user, code="5678", type="reset")
        
        data = {
            "phone": "01806779331",
            "country_code": "BD",
            "code": "5678",
            "password": "NewSecurePassword123",
            "confirm_password": "NewSecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/reset-password/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_verified)
        self.assertTrue(user.check_password("NewSecurePassword123"))

    def test_change_password_success(self):
        """Test authenticated user successfully changes password"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=True,
            is_verified=True
        )
        self.client.force_authenticate(user=user)
        
        data = {
            "current_password": "SecurePassword123",
            "new_password": "NewSecurePassword123",
            "confirm_password": "NewSecurePassword123"
        }
        response = self.client.post('/v1/accounts/auth/password-change/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewSecurePassword123"))

    def test_profile_retrieval_and_update(self):
        """Test GET and PATCH on profile for authenticated user"""
        user = User.objects.create_user(
            phone="01806779331",
            country_code="BD",
            password="SecurePassword123",
            name="Test User",
            is_active=True
        )
        self.client.force_authenticate(user=user)
        
        # GET Profile
        response = self.client.get('/v1/accounts/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Test User")
        
        # PATCH Profile
        patch_data = {
            "name": "Updated Name",
            "gender": "Male"
        }
        response = self.client.patch('/v1/accounts/auth/profile/', patch_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Updated Name")
        self.assertEqual(response.data['gender'], "Male")

    def test_cleanup_unverified_users_task(self):
        """Test task deletes unverified users older than 15 minutes, keeps active/new/deactivated ones"""
        # 1. Unverified user created 20 minutes ago (should be deleted)
        u1 = User.objects.create_user(
            phone="01806779331", country_code="BD", password="Password123", name="U1", is_active=False
        )
        u1.date_joined = timezone.now() - timezone.timedelta(minutes=20)
        u1.save()
        
        # 2. Unverified user created 5 minutes ago (should be kept)
        u2 = User.objects.create_user(
            phone="01806779332", country_code="BD", password="Password123", name="U2", is_active=False
        )
        
        # 3. Verified but manually deactivated user (should be kept)
        u3 = User.objects.create_user(
            phone="01806779333", country_code="BD", password="Password123", name="U3", is_active=False
        )
        u3.is_verified = True
        u3.date_joined = timezone.now() - timezone.timedelta(minutes=30)
        u3.save()
        
        # Run cleanup task
        res = cleanup_unverified_users()
        self.assertEqual(res, "Deleted 1 unverified users.")
        
        # Verify which users exist
        self.assertFalse(User.objects.filter(id=u1.id).exists())
        self.assertTrue(User.objects.filter(id=u2.id).exists())
        self.assertTrue(User.objects.filter(id=u3.id).exists())
