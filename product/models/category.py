from django.db import models
from django.conf import settings
from slugify import slugify


class ParentProductCategory(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.db import IntegrityError, transaction
        from product.utils import set_unique_slug
        
        attempts = 5
        counter = 1
        while attempts > 0:
            set_unique_slug(self)
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                err_msg = str(e).lower()
                if 'slug' in err_msg or 'unique' in err_msg:
                    from slugify import slugify
                    base_slug = slugify(self.name)
                    self.slug = f"{base_slug}-{counter}"
                    counter += 1
                    attempts -= 1
                else:
                    raise e
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    parent = models.ForeignKey(ParentProductCategory, on_delete=models.CASCADE, related_name='categories', null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.db import IntegrityError, transaction
        from product.utils import set_unique_slug
        
        attempts = 5
        counter = 1
        while attempts > 0:
            set_unique_slug(self)
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                err_msg = str(e).lower()
                if 'slug' in err_msg or 'unique' in err_msg:
                    from slugify import slugify
                    base_slug = slugify(self.name)
                    self.slug = f"{base_slug}-{counter}"
                    counter += 1
                    attempts -= 1
                else:
                    raise e
        super().save(*args, **kwargs)


class ProductCategoryOption(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    product_category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='options')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_options')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.product_category.name} - {self.name} -id {self.id}"

    def save(self, *args, **kwargs):
        from django.db import IntegrityError, transaction
        from product.utils import set_unique_slug
        
        attempts = 5
        counter = 1
        while attempts > 0:
            set_unique_slug(self)
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                err_msg = str(e).lower()
                if 'slug' in err_msg or 'unique' in err_msg:
                    from slugify import slugify
                    base_slug = slugify(self.name)
                    self.slug = f"{base_slug}-{counter}"
                    counter += 1
                    attempts -= 1
                else:
                    raise e
        super().save(*args, **kwargs)


class ProductCategoryOptionValue(models.Model):
    product_category_option = models.ForeignKey(ProductCategoryOption, on_delete=models.CASCADE, related_name='values')
    value = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_option_values')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.product_category_option.name} - {self.value} -id {self.id}"


class ProductCategoryOptionAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='option_audits')
    action = models.CharField(max_length=50)  # 'create_option' or 'create_value'
    option_name = models.CharField(max_length=200)
    value_name = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.option_name} - {self.value_name or ''}"
