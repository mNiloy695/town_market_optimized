import logging
from django.db import transaction
from django.utils import timezone

from chat.models import Message
from .broadcast import broadcast_to_conversation

logger = logging.getLogger(__name__)


class ReadReceiptService:
    @staticmethod
    def mark_conversation_as_read(conversation_id: str, user) -> int:
        """
        Marks all messages in the conversation sent by the other participant as read.
        """
        logger.info(f"Marking conversation {conversation_id} as read by user {getattr(user, 'id', None)}")

        from chat.selectors import get_conversation_for_user
        conversation = get_conversation_for_user(conversation_id, user)

        now = timezone.now()
        with transaction.atomic():
            # Find and update unread messages not sent by this user
            unread_messages = Message.objects.filter(
                conversation=conversation,
                is_read=False
            ).exclude(sender=user)

            count = unread_messages.update(
                is_read=True,
                read_at=now
            )

            if count > 0:
                # Broadcast read notification
                event_payload = {
                    "type": "messages_read",
                    "conversation_id": conversation_id,
                    "reader_id": user.id,
                    "read_at": now.isoformat()
                }
                transaction.on_commit(lambda: broadcast_to_conversation(conversation_id, event_payload))
                logger.info(f"Marked {count} messages in conversation {conversation_id} as read.")
            else:
                logger.info(f"No unread messages from other participant in conversation {conversation_id}.")

        return count
