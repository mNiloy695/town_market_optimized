from django.db import models
from django.contrib.auth import get_user_model
User=get_user_model()
# Create your models here.

RATING=(
    ("1","⭐"),
    ("2","⭐⭐"),
    ("3","⭐⭐⭐"),
    ("4","⭐⭐⭐⭐"),
    ("5","⭐⭐⭐⭐⭐")
)

class Review(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="reviews")
    product=models.ForeignKey("product.Product",on_delete=models.CASCADE,related_name="reviews")
    rating=models.CharField(max_length=1,choices=RATING)
    review_text=models.TextField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user} - {self.product} - {self.rating}"
