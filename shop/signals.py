from django.dispatch import receiver
from django.db.models.signals import post_save,post_delete
from .models import RequestForShop,Shop

@receiver(post_save,sender=RequestForShop)
def update_user_status(sender,instance,created,**kwargs):
    if created:
        user=instance.user
        user.is_request_for_shop="request_pending"
        user.save(update_fields=['is_request_for_shop'])
    
    if not created and instance.status=='approved':
        user=instance.user
        user.is_request_for_shop="request_approved"
        user.role="seller"
        user.save(update_fields=['is_request_for_shop','role'])
        instance.shop.status="approved"
        instance.shop.save(update_fields=['status'])
        instance.delete()
    
    if not created and instance.status=='rejected':
        user=instance.user
        user.is_request_for_shop="request_not_requested"
        user.role="buyer"
        user.save(update_fields=['is_request_for_shop','role'])
        instance.shop.delete()
        instance.delete()

@receiver(post_delete, sender=Shop)
def update_user_status_on_delete(sender, instance, **kwargs):
    if hasattr(instance, 'owner') and instance.owner:
        user = instance.owner
        user.is_request_for_shop = "request_not_requested"
        user.role="buyer"
        user.save(update_fields=['is_request_for_shop','role'])