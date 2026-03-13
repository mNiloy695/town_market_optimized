from django.contrib import admin
from .models import Category,Market,Shop,RequestForShop
# Register your models here.

admin.site.register(Category)
admin.site.register(Market)
admin.site.register(Shop)
admin.site.register(RequestForShop)