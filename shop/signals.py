import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Shop, RequestForShop
from product.models import Product

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Shop)
def deactivate_shop_products(sender, instance, **kwargs):
    """
    When a Shop is deactivated (is_active becomes False or is_deactivated becomes True),
    also deactivate all related products so they are not visible until the shop is reactivated.
    """
    # Get the existing instance from the database if this is an update
    if instance.pk:
        try:
            old_instance = Shop.objects.get(pk=instance.pk)
        except Shop.DoesNotExist:
            old_instance = None
    else:
        old_instance = None

    if old_instance:
        # Check if is_active is becoming False
        is_active_changed = old_instance.is_active and not instance.is_active
        # Check if is_deactivated is becoming True
        is_deactivated_changed = not old_instance.is_deactivated and instance.is_deactivated

        if is_active_changed or is_deactivated_changed:
            # Deactivate all products from this shop
            Product.objects.filter(shop=instance).update(is_active=False)
            logger.info(
                "Deactivated products for shop %s (is_active=%s, is_deactivated=%s)",
                instance.pk, instance.is_active, instance.is_deactivated,
            )
        # New shop creation - if marked deactivated from the start, deactivate products
        if instance.is_deactivated:
            Product.objects.none()  # No products yet, nothing to do
            # We'll handle this via post_save if needed


@receiver(post_save, sender=RequestForShop)
def update_user_status_on_request(sender, instance, **kwargs):
    user = instance.user
    shop = instance.shop
    if instance.status == 'approved':
        user.is_request_for_shop = 'request_approved'
        user.role = 'seller'
        shop.status = 'approved'
        shop.is_active = True
        shop.is_deactivated = False
        shop.save(update_fields=['status', 'is_active', 'is_deactivated'])
    elif instance.status == 'pending':
        user.is_request_for_shop = 'request_pending'
        shop.status = 'pending'
        shop.save(update_fields=['status'])
    else:  # rejected
        user.is_request_for_shop = 'request_not_requested'
        user.role = 'buyer'
        shop.status = 'rejected'
        shop.is_active = False
        shop.is_deactivated = True
        shop.save(update_fields=['status', 'is_active', 'is_deactivated'])
    user.save(update_fields=['is_request_for_shop', 'role'])


@receiver(post_save, sender=Shop)
def update_user_status_on_shop(sender, instance, **kwargs):
    user = instance.owner
    if instance.status == 'approved':
        user.is_request_for_shop = 'request_approved'
        user.role = 'seller'
    elif instance.status == 'pending':
        user.is_request_for_shop = 'request_pending'
    else:  # rejected
        user.is_request_for_shop = 'request_not_requested'
        user.role = 'buyer'
    user.save(update_fields=['is_request_for_shop', 'role'])