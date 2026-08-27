import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_conversations'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-last_message_at']
        constraints = [
            models.UniqueConstraint(
                fields=['buyer', 'seller'],
                name='unique_buyer_seller_conversation'
            ),
            models.CheckConstraint(
                condition=~models.Q(buyer=models.F('seller')),
                name='buyer_cannot_be_seller'
            )
        ]
        indexes = [
            models.Index(fields=['buyer', '-last_message_at']),
            models.Index(fields=['seller', '-last_message_at']),
        ]

    def __str__(self):
        return f"Chat: Buyer {self.buyer.phone} ↔ Seller {self.seller.phone}"


class MessageType(models.TextChoices):
    TEXT = 'text', 'Text'
    MEDIA = 'media', 'Media'
    PRODUCT_LINK = 'product_link', 'Product Link'
    SYSTEM = 'system', 'System'


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        null=True,
        blank=True
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )
    content = models.TextField(blank=True)
    product = models.ForeignKey(
        'product.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_inquiries'
    )
    attachment = models.FileField(
        upload_to='chat_attachments/',
        null=True,
        blank=True
    )
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'is_read']),
            models.Index(fields=['sender', 'created_at']),
        ]

    def __str__(self):
        sender_str = self.sender.phone if self.sender else "SYSTEM"
        return f"Msg {self.id} by {sender_str} in {self.conversation.id}"
