from django.db import models


GENDER = (
    ("Male", "Male"),
    ("Female", "Female"),
    ("Intersex", "Intersex")
)


class UserProfile(models.Model):
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name="profile"
    )
    avatar = models.ImageField(upload_to="profile_image", null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(choices=GENDER, max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.phone}"
