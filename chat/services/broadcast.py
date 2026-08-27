import logging
import uuid
from decimal import Decimal
from datetime import datetime, date
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def broadcast_to_conversation(conversation_id: str, event_data: dict):
    """
    Helper to send real-time event notifications to a conversation's channel group.
    """
    logger.info(f"Broadcasting event '{event_data.get('type')}' to conversation {conversation_id}")

    def clean_json_data(obj):
        if isinstance(obj, dict):
            return {k: clean_json_data(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_json_data(item) for item in obj]
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return obj

    try:
        cleaned_data = clean_json_data(event_data)
        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"chat_{conversation_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "chat_message_event",
                    "data": cleaned_data
                }
            )
        else:
            logger.warning(f"No channel layer configured when attempting broadcast to {conversation_id}")
    except Exception as e:
        logger.error(f"Error during WebSocket broadcast to conversation {conversation_id}: {e}", exc_info=True)
