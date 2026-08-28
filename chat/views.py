import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import FileResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import AccessToken

from chat.models import Conversation, Message
from chat.serializers import ConversationSerializer, MessageSerializer
from chat.selectors import get_user_conversations, get_conversation_messages
from chat.services import ConversationService, MessageService
from chat.permissions import IsConversationParticipant

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatMessagePagination(PageNumberPagination):
    """
    Standard pagination class for historical message pagination.
    """
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class ConversationListCreateView(ListCreateAPIView):
    """
    GET: List all conversations for the authenticated user, ordered by last_message_at DESC.
    POST: Start/retrieve a conversation with a seller (accepts optional product_id context).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return get_user_conversations(self.request.user)

    def create(self, request, *args, **kwargs):
        seller_id = request.data.get('seller_id')
        product_id = request.data.get('product_id')

        if not seller_id:
            return Response(
                {"seller_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conversation, created = ConversationService.get_or_create_conversation(
                buyer=request.user,
                seller_id=int(seller_id),
                product_id=int(product_id) if product_id else None
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid format for seller_id or product_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as e:
            return Response(
                {"error": e.message if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(conversation)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class MessageListView(ListAPIView):
    """
    GET: List all historical messages in a conversation, paginated, checking user membership.
    """
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    serializer_class = MessageSerializer
    pagination_class = ChatMessagePagination

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        after = self.request.query_params.get('after')
        try:
            return get_conversation_messages(conversation_id, self.request.user, after=after)
        except PermissionDenied as e:
            logger.warning(f"Unauthorized messages access attempt on conversation {conversation_id} by user {self.request.user.id}")
            raise e


class MediaUploadView(APIView):
    """
    POST: Upload a file/media message to a conversation. Checks membership and 10 MB file limits.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {"file": "No file was submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # MessageService checks size limit, MIME types, and conversation membership
            message = MessageService.create_media_message(
                conversation_id=conversation_id,
                sender=request.user,
                file_obj=file_obj
            )
        except ValidationError as e:
            return Response(
                {"error": e.messages[0] if hasattr(e, 'messages') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionDenied as e:
            logger.warning(f"Unauthorized media upload attempt on conversation {conversation_id} by user {request.user.id}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = MessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SecureAttachmentDownloadView(APIView):
    """
    GET: Securely download/stream a media message attachment.
    Supports JWT header authentication or short-lived query param: ?token=<JWT>.
    """
    permission_classes = [AllowAny]

    def get(self, request, message_id):
        # 1. Resolve user from either headers or query parameter token
        user = request.user
        token = request.query_params.get('token')

        if (not user or getattr(user, 'is_anonymous', False)) and token:
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id, is_active=True)
            except Exception as e:
                logger.debug(f"Secure download JWT validation failed: {e}")
                return Response(
                    {"error": "Invalid or expired token."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # Re-verify user authentication state
        if not user or getattr(user, 'is_anonymous', False):
            return Response(
                {"error": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Retrieve Message
        try:
            message = Message.objects.select_related('conversation').get(pk=message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": "Message not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Verify object-level authorization (must be buyer or seller)
        from chat.selectors import verify_membership
        if not verify_membership(user, message.conversation):
            logger.warning(f"Unauthorized attachment download block. User {user.id} tried accessing message {message.id}")
            return Response(
                {"error": "You are not authorized to view this attachment."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not message.attachment:
            return Response(
                {"error": "This message does not contain an attachment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Stream File Response securely
        try:
            response = FileResponse(
                message.attachment.open('rb'),
                content_type=message.file_type or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{message.file_name or "download"}"'
            return response
        except Exception as e:
            logger.error(f"Error opening attachment file: {e}", exc_info=True)
            return Response(
                {"error": "Could not read file from storage backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
