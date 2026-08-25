from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import NumberParseException


class CustomUserManager(BaseUserManager):
    def create_user(self, phone, country_code, password=None, **extra_fields):
        if not phone:
            raise ValueError("The Phone number must be set")
        if not country_code:
            raise ValueError("The Country Code must be set")

        try:
            phone_number = PhoneNumber.from_string(phone, region=country_code)
            if not phone_number.is_valid():
                raise ValueError("Invalid phone number")
        except NumberParseException:
            raise ValueError("Invalid phone number or country code")

        user = self.model(
            phone=phone_number,
            country_code=country_code,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, country_code, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, country_code, password, **extra_fields)


ROLE = (
    ('buyer', 'buyer'),
    ('seller', 'seller')
)
STATUS_CHOICES = (
    ('request_pending', 'request_pending'),
    ('request_approved', 'request_approved'),
    ("request_not_requested", "request_not_requested"),
)


class CustomUser(AbstractUser, PermissionsMixin):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, unique=True)
    country_code = models.CharField(max_length=5)
    role = models.CharField(max_length=20, choices=ROLE, default="buyer")
    is_request_for_shop = models.CharField(max_length=25, choices=STATUS_CHOICES, default='request_not_requested')
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    birth_date = models.DateField(blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    otp_locked_until = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = 'phone'
    username = None
    REQUIRED_FIELDS = ['country_code', 'name']

    # ✅ Fix: related_name clashes with auth.User - must be unique
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='accounts_user_groups',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='accounts_user_permissions',
        blank=True,
    )

    objects = CustomUserManager()

    def __str__(self):
        return str(self.phone)

    def is_otp_locked(self):
        from django.utils import timezone
        return self.otp_locked_until is not None and timezone.now() < self.otp_locked_until

    class Meta:
        ordering = ['-date_joined']
