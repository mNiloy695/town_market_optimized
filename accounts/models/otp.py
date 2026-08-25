from django.db import models


OTP_TYPE = (
    ('active', 'active'),
    ('reset', 'reset'),
)


class OTP(models.Model):
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name="otps",
        null=True
    )
    code = models.CharField(max_length=4)
    type = models.CharField(choices=OTP_TYPE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def is_expired(self):
        from django.utils import timezone
        expiration_time = self.created_at + timezone.timedelta(minutes=3)
        return timezone.now() > expiration_time

    def is_locked(self):
        from django.utils import timezone
        if self.user and self.user.otp_locked_until and timezone.now() < self.user.otp_locked_until:
            return True
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def record_failed_attempt(self):
        from django.utils import timezone
        self.failed_attempts += 1
        if self.user and self.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.user.otp_locked_until = timezone.now() + timezone.timedelta(minutes=self.LOCKOUT_MINUTES)
            self.user.save(update_fields=['otp_locked_until'])
            self.locked_until = self.user.otp_locked_until
        self.save(update_fields=['failed_attempts', 'locked_until'])

    def reset_failed_attempts(self):
        self.failed_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_attempts', 'locked_until'])

    def __str__(self):
        return f"OTP - {self.code}"

    class Meta:
        ordering = ["-created_at"]
