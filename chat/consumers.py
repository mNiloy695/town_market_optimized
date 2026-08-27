import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from chat.models import Conversation
from chat.services import MessageService, ReadReceiptService
from chat.selectors import verify_membership

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer handling WebSocket connections for a specific Conversation.
    Validates user authentication and membership, receives events, and broadcasts them.
    Also tracks online presence and typing indicators.
    """
    async def connect(self):
        self.user = self.scope.get('user')
        self.user_id = getattr(self.user, 'id', None)

        # Parse conversation_id UUID from URL route
        try:
            self.conversation_id = str(self.scope['url_route']['kwargs']['conversation_id'])
        except (KeyError, ValueError) as e:
            logger.warning(f"WebSocket connection failed: invalid route parameter. Error: {e}")
            await self.close(code=4000)
            return

        self.room_group_name = f"chat_{self.conversation_id}"

        # 1. Enforce Authentication Check
        if not self.user or self.user.is_anonymous:
            logger.warning("WebSocket connection rejected: Anonymous User.")
            await self.close(code=4001)  # Policy Violation / Unauthorized
            return

        # 2. Enforce Conversation Authorization Check
        is_member = await self.check_membership(self.conversation_id, self.user)
        if not is_member:
            logger.warning(f"WebSocket connection rejected: User {self.user.id} is not a member of conversation {self.conversation_id}.")
            await self.close(code=4003)  # Forbidden / Unauthorized Resource Access
            return

        # Join the conversation channel group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 3. Join the presence group for this user (so other conversations they
        #    are part of can be notified when they come online)
        self.presence_group_name = f"presence_{self.user_id}"
        await self.channel_layer.group_add(
            self.presence_group_name,
            self.channel_name
        )

        await self.accept()

        # 4. Notify other participants that this user is now online
        await self.broadcast_online_status(self.user_id, True)

        logger.info(f"WebSocket connected: User {getattr(self.user, 'phone', 'Unknown')} joined {self.room_group_name}")

    async def disconnect(self, close_code):
        # Leave channel layer group(s)
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            # Notify other participants that this user is now offline
            if getattr(self, 'user_id', None):
                await self.broadcast_online_status(self.user_id, False)

        if hasattr(self, 'presence_group_name'):
            await self.channel_layer.group_discard(
                self.presence_group_name,
                self.channel_name
            )

        logger.info(f"WebSocket disconnected: User {getattr(self.user, 'phone', 'Anonymous') if hasattr(self, 'user') else 'Anonymous'} left {self.room_group_name} with code {close_code}")

    def get_participant_user_ids(self, conversation_id, current_user_id):
        """
        Returns the user IDs (excluding current_user_id) participating in the conversation.
        """
        try:
            from chat.models import Conversation as Conv
            conv = Conv.objects.get(pk=conversation_id)
            ids = {conv.buyer_id, conv.seller_id}
            ids.discard(current_user_id)
            return list(ids)
        except Conv.DoesNotExist:
            return []

    async def broadcast_online_status(self, user_id, is_online):
        """
        Sends an online/offline presence event to the other participant of the
        conversation this user is connected to.
        """
        participant_ids = await self.get_list_conversation_participants(self.conversation_id, user_id)
        for pid in participant_ids:
            await self.channel_layer.group_send(
                f"presence_{pid}",
                {
                    "type": "user_presence_event",
                    "data": {
                        "type": "presence",
                        "user_id": user_id,
                        "is_online": is_online,
                        "conversation_id": self.conversation_id,
                    },
                },
            )

    async def user_presence_event(self, event):
        """Receives a presence broadcast and forwards it to the client."""
        await self.send_json(event["data"])

    async def typing_event_received(self, event):
        """Receives a typing indicator broadcast and forwards it to the client."""
        await self.send_json(event["data"])

    @database_sync_to_async
    def get_list_conversation_participants(self, conversation_id, user_id):
        """Get the other participant's ID for this conversation."""
        return self.get_participant_user_ids(conversation_id, user_id)

    async def receive_json(self, content):
        """
        Receives events from the client WebSocket.
        """
        if not content or not isinstance(content, dict):
            await self.send_json({"error": "Invalid message format."})
            return

        action = content.get('action')

        try:
            if action == 'send_message':
                message_content = content.get('content', '')
                await self.create_text_message(self.conversation_id, self.user, message_content)
            elif action == 'read_messages':
                await self.mark_messages_read(self.conversation_id, self.user)
            elif action == 'typing':
                await self.handle_typing(content)
            else:
                await self.send_json({
                    "error": "Invalid action. Supported actions: 'send_message', 'read_messages', 'typing'."
                })
        except ValidationError as e:
            await self.send_json({
                "error": e.messages[0] if hasattr(e, 'messages') else str(e)
            })
        except Exception as e:
            logger.error(f"Error executing action {action} in WebSocket: {e}", exc_info=True)
            await self.send_json({
                "error": "Internal server error processing action."
            })

    async def handle_typing(self, content):
        """
        Broadcasts a typing indicator to the other participant in the conversation.
        Client sends {'action': 'typing', 'is_typing': true|false}.
        """
        is_typing = bool(content.get('is_typing', False))
        participant_ids = await self.get_list_conversation_participants(self.conversation_id, self.user_id)
        for pid in participant_ids:
            await self.channel_layer.group_send(
                f"presence_{pid}",
                {
                    "type": "typing_event_received",
                    "data": {
                        "type": "typing",
                        "user_id": self.user_id,
                        "is_typing": is_typing,
                        "conversation_id": self.conversation_id,
                    },
                },
            )

    async def chat_message_event(self, event):
        """
        Receive event broadcast from the channel group and forward it as JSON to the client.
        """
        await self.send_json(event['data'])

    @database_sync_to_async
    def check_membership(self, conversation_id: str, user) -> bool:
        try:
            conversation = Conversation.objects.get(pk=conversation_id)
            return verify_membership(user, conversation)
        except (Conversation.DoesNotExist, ValidationError, ValueError):
            return False

    @database_sync_to_async
    def create_text_message(self, conversation_id: str, sender, content: str):
        MessageService.create_text_message(conversation_id, sender, content)

    @database_sync_to_async
    def mark_messages_read(self, conversation_id: str, user):
        ReadReceiptService.mark_conversation_as_read(conversation_id, user)
