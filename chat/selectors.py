from django.db.models import Q, Count, OuterRef, Subquery
from django.core.exceptions import PermissionDenied
from chat.models import Conversation, Message


def verify_membership(user, conversation: Conversation) -> bool:
    """
    Verifies if the given user is a participant (buyer or seller) in the conversation.
    """
    from chat.permissions import ChatPermissionValidator
    return ChatPermissionValidator.verify_membership(user, conversation)

def get_conversation_for_user(conversation_id: str, user) -> Conversation:
    """
    Retrieves a conversation by ID, verifying that the user is a participant.
    Raises PermissionDenied if not authorized.
    """
    try:
        conversation = Conversation.objects.select_related(
            'buyer', 'seller', 'buyer__profile', 'seller__profile'
        ).get(pk=conversation_id)
    except Conversation.DoesNotExist:
        raise PermissionDenied("Conversation not found.")

    from chat.permissions import ChatPermissionValidator
    ChatPermissionValidator.validate_can_access_conversation(user, conversation)

    return conversation



def get_user_conversations(user):
    """
    Retrieves all conversations for a given user, ordered by last_message_at DESC.
    Optimized with select_related, Count, and Subquery annotations to prevent N+1 queries.
    """
    last_msg_qs = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at')

    return Conversation.objects.filter(
        Q(buyer=user) | Q(seller=user)
    ).select_related(
        'buyer', 'seller', 'buyer__profile', 'seller__profile'
    ).annotate(
        unread_count=Count(
            'messages',
            filter=~Q(messages__sender=user) & Q(messages__is_read=False)
        ),
        last_msg_id=Subquery(last_msg_qs.values('id')[:1]),
        last_msg_content=Subquery(last_msg_qs.values('content')[:1]),
        last_msg_type=Subquery(last_msg_qs.values('message_type')[:1]),
        last_msg_created_at=Subquery(last_msg_qs.values('created_at')[:1]),
    ).order_by('-last_message_at')


def get_conversation_messages(conversation_id: str, user, after=None):
    """
    Retrieves all messages in a conversation, verifying user authorization.
    Ordered by -created_at (newest first for pagination).
    If 'after' is provided, only messages created after that timestamp are returned.
    """
    conversation = get_conversation_for_user(conversation_id, user)
    qs = Message.objects.filter(conversation=conversation).select_related(
        'sender', 'sender__profile', 'product', 'product__shop'
    )
    if after:
        qs = qs.filter(created_at__gt=after)
    return qs.order_by('-created_at')


def is_user_online(user_id) -> bool:
    """
    Determines whether a user currently has at least one active WebSocket
    connection (i.e. is online) by inspecting their presence group in the
    channel layer. Returns False if the channel layer is unavailable or the
    user has no active connections.
    """
    if not user_id:
        return False

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    if not channel_layer:
        return False

    try:
        channels = async_to_sync(channel_layer.group_channels)(f"presence_{user_id}")
        return bool(channels)
    except Exception:
        return False
