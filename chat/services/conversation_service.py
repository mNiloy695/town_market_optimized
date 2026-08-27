import logging
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from chat.models import Conversation, Message, MessageType
from product.models.product import Product
from .broadcast import broadcast_to_conversation

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationService:
    @staticmethod
    def get_or_create_conversation(buyer, seller_id: int, product_id: int = None) -> tuple[Conversation, bool]:
        """
        Retrieves or creates a Conversation between a buyer and a seller.
        Performs strict role and status validation.
        Optionally injects a product inquiry message with duplicate protection.
        """
        logger.info(
            f"Attempting to get or create conversation between buyer {getattr(buyer, 'id', None)} "
            f"and seller_id {seller_id} (product_id: {product_id})"
        )

        from chat.permissions import ChatPermissionValidator

        existing_conversation, seller, product = ChatPermissionValidator.validate_can_initiate_conversation(
            buyer=buyer,
            seller_id=seller_id,
            product_id=product_id
        )

        if existing_conversation:
            conversation = existing_conversation
            created = False
        else:
            with transaction.atomic():
                conversation, created = Conversation.objects.get_or_create(
                    buyer=buyer,
                    seller=seller
                )
                logger.info(f"Conversation {conversation.id} resolved. Created new record: {created}")

        # Inject product inquiry or system message inside transaction block
        with transaction.atomic():
            # Inject product inquiry if provided
            if product:
                # Idempotency / De-duplication check:
                # Do not insert if there is a product inquiry for the same product in the last 5 minutes
                five_minutes_ago = timezone.now() - timezone.timedelta(minutes=5)
                duplicate_exists = Message.objects.filter(
                    conversation=conversation,
                    message_type=MessageType.PRODUCT_LINK,
                    product=product,
                    created_at__gte=five_minutes_ago
                ).exists()

                if not duplicate_exists:
                    # Create the product inquiry card message
                    inquiry_msg = Message.objects.create(
                        conversation=conversation,
                        sender=buyer,
                        message_type=MessageType.PRODUCT_LINK,
                        product=product,
                        content=f"Inquiry about product: {product.name}",
                        is_read=False
                    )
                    # Update conversation last message timestamp
                    conversation.last_message_at = inquiry_msg.created_at
                    conversation.save(update_fields=['last_message_at'])

                    # Prepare and broadcast the event
                    from chat.serializers import MessageSerializer
                    serializer = MessageSerializer(inquiry_msg)
                    event_payload = {
                        "type": "chat_message",
                        "message": serializer.data
                    }
                    transaction.on_commit(lambda: broadcast_to_conversation(str(conversation.id), event_payload))
                    logger.info(f"Injected product inquiry message {inquiry_msg.id} into conversation {conversation.id}")
                else:
                    logger.info(f"Skipped duplicate product inquiry link creation for product {product.id} in conversation {conversation.id}")

            # If it's a brand new conversation and no product inquiry was created, we can inject a system message
            elif created:
                system_msg = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    message_type=MessageType.SYSTEM,
                    content="Conversation started."
                )
                conversation.last_message_at = system_msg.created_at
                conversation.save(update_fields=['last_message_at'])

                # Broadcast system message
                from chat.serializers import MessageSerializer
                serializer = MessageSerializer(system_msg)
                event_payload = {
                    "type": "chat_message",
                    "message": serializer.data
                }
                transaction.on_commit(lambda: broadcast_to_conversation(str(conversation.id), event_payload))
                logger.info(f"Injected system message {system_msg.id} into conversation {conversation.id}")

        return conversation, created

