from slugify import slugify

def set_unique_slug(instance):
    """
    Generates a unique slug for a model instance based on its name.
    Does not modify slug if instance already has one and is persisted.
    """
    if not instance.name:
        return
    if instance.pk and instance.slug:
        return
    base_slug = slugify(instance.name)
    slug = base_slug
    counter = 1
    while instance.__class__.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    instance.slug = slug
