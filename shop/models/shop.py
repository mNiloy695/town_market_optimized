from django.db import models
from django.contrib.auth import get_user_model
from slugify import slugify
from .market import Market, Category

User = get_user_model()

STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class Shop(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    logo = models.ImageField(upload_to='shop_logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='shop_cover_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(blank=True, null=True)
    closing_time = models.TimeField(blank=True, null=True)
    address = models.CharField(max_length=700)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='shops')
    Category = models.ManyToManyField(Category, related_name='shops')
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shop')
    is_deactivated = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class RequestForShop(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.user.name
