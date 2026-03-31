from django.db import models
from slugify import slugify
from django_filters.rest_framework import DjangoFilterBackend
# Create your models here.

class ParentProductCategory(models.Model):
    name=models.CharField(max_length=200)
    slug=models.SlugField(max_length=200,unique=True,blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
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


class ProductCategory(models.Model):
    name=models.CharField(max_length=200)
    slug=models.SlugField(max_length=200,unique=True,blank=True,null=True)
    parent=models.ForeignKey('ParentProductCategory',on_delete=models.CASCADE,related_name='categories',null=True)
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
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


class ProductImage(models.Model):
    product=models.ForeignKey('Product',on_delete=models.CASCADE,related_name='images')
    image=models.ImageField(upload_to='product_images/')
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
    def __str__(self):
        return f"{self.product.name} - {self.id}"


class Product(models.Model):
    name=models.CharField(max_length=200)
    slug=models.SlugField(max_length=200,unique=True,blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
    shop=models.ForeignKey('shop.Shop',on_delete=models.CASCADE,related_name='products')
    sub_category=models.ForeignKey(ProductCategory,on_delete=models.CASCADE,related_name='products')

    def __str__(self):
        return f'{self.name} - {self.id}'
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


#option variant 
class ProductCategoryOption(models.Model):
    name=models.CharField(max_length=200)
    slug=models.SlugField(max_length=200,unique=True,blank=True,null=True)
    product_category=models.ForeignKey(ProductCategory,on_delete=models.CASCADE,related_name='options')
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
    def __str__(self):
        return f"{self.product_category.name} - {self.name} -id {self.id}"
    
    def save(self,*args,**kwargs):
        if self.name:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    




class ProductCategoryOptionValue(models.Model):
    product_category_option=models.ForeignKey(ProductCategoryOption,on_delete=models.CASCADE,related_name='values')
    value=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True,null=True,blank=True)
    def __str__(self):
        return f"{self.product_category_option.name} - {self.value} -id {self.id}"



class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    stock=models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - Variant {self.id}"

class ProductVariantOptionValue(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='option_values')
    option_value = models.ForeignKey(ProductCategoryOptionValue, on_delete=models.CASCADE, related_name='variant_links')

    class Meta:
        unique_together = ('variant', 'option_value')

    def __str__(self):
        return f"{self.variant} - {self.option_value.value}"

    def validate_option_value(self):
        if self.option_value.product_category_option.product_category != self.variant.product.sub_category:
            raise serializers.ValidationError({"detail": "You are not authorized to create a product because you are not the owner of the shop."})
        super().validate_option_value()

        






