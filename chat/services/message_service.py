import os
import mimetypes
import logging
from django.db import transaction
from django.core.exceptions import ValidationError

from chat.models import Message, MessageType
from .broadcast import broadcast_to_conversation

logger = logging.getLogger(__name__)


class MessageService:
    @staticmethod
    def create_text_message(conversation_id: str, sender, content: str) -> Message:
        """
        Creates a text message within a conversation.
        """
        logger.info(f"Creating text message in conversation {conversation_id} by user {getattr(sender, 'id', None)}")

        # Clean and validate content
        if not content or not isinstance(content, str):
            logger.warning(f"Message creation failed: empty content type {type(content)}")
            raise ValidationError("Message content cannot be empty.")
        content = content.strip()
        if not content:
            logger.warning("Message creation failed: empty content string")
            raise ValidationError("Message content cannot be empty.")
        if len(content) > 5000:
            logger.warning(f"Message creation failed: content length {len(content)} exceeds 5000 chars limit")
            raise ValidationError("Message exceeds maximum length of 5000 characters.")

        # Resolve conversation and verify membership
        from chat.selectors import get_conversation_for_user
        conversation = get_conversation_for_user(conversation_id, sender)

        # Centralized permission validation
        from chat.permissions import ChatPermissionValidator
        ChatPermissionValidator.validate_can_send_message(sender, conversation)

        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender=sender,
                message_type=MessageType.TEXT,
                content=content
            )
            # Update last_message_at
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=['last_message_at'])

            # Broadcast
            from chat.serializers import MessageSerializer
            serializer = MessageSerializer(message)
            event_payload = {
                "type": "chat_message",
                "message": serializer.data
            }
            transaction.on_commit(lambda: broadcast_to_conversation(conversation_id, event_payload))
            logger.info(f"Text message {message.id} created and broadcast scheduled.")

        return message

    @staticmethod
    def create_media_message(conversation_id: str, sender, file_obj) -> Message:
        """
        Handles saving a uploaded file/media message, enforcing size limits and security controls.
        """
        logger.info(f"Creating media message in conversation {conversation_id} by user {getattr(sender, 'id', None)}")

        # Enforce strict 10 MB limit
        MAX_SIZE = 10 * 1024 * 1024  # 10,485,760 bytes
        if file_obj.size >= MAX_SIZE:
            logger.warning(f"Media upload failed: file size {file_obj.size} bytes exceeds 10MB limit")
            raise ValidationError("File size exceeds the maximum limit of 10 MB.")

        # Resolve conversation and verify membership
        from chat.selectors import get_conversation_for_user
        conversation = get_conversation_for_user(conversation_id, sender)

        # Centralized permission validation
        from chat.permissions import ChatPermissionValidator
        ChatPermissionValidator.validate_can_send_message(sender, conversation)

        # Normalize and sanitize filename
        original_name = os.path.basename(file_obj.name)

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(original_name)
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Reject dangerous file types (e.g. executables or scripts)
        banned_extensions = ['.exe', '.sh', '.bat', '.cmd', '.py', '.js', '.html', '.htm', '.php']
        _, ext = os.path.splitext(original_name.lower())
        if ext in banned_extensions or 'javascript' in mime_type or 'html' in mime_type:
            logger.warning(f"Media upload failed: banned extension/mimetype {original_name} ({mime_type})")
            raise ValidationError("Uploaded file type is not allowed.")

        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender=sender,
                message_type=MessageType.MEDIA,
                attachment=file_obj,
                file_name=original_name,
                file_type=mime_type,
                file_size=file_obj.size
            )
            # Update last_message_at
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=['last_message_at'])

            # Broadcast
            from chat.serializers import MessageSerializer
            serializer = MessageSerializer(message)
            event_payload = {
                "type": "chat_message",
                "message": serializer.data
            }
            transaction.on_commit(lambda: broadcast_to_conversation(conversation_id, event_payload))
            logger.info(f"Media message {message.id} created and broadcast scheduled. Filename: {original_name}")

        return message
