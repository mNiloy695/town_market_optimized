import logging
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework import permissions
from chat.models import Conversation
from product.models.product import Product

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatPermissionValidator:
    @staticmethod
    def verify_membership(user, conversation: Conversation) -> bool:
        """
        Verifies if the given user is a participant (buyer or seller) in the conversation.
        """
        if not user or getattr(user, 'is_anonymous', False):
            return False
        return conversation.buyer_id == user.id or conversation.seller_id == user.id

    @classmethod
    def validate_can_access_conversation(cls, user, conversation: Conversation) -> None:
        """
        Validates if the user can access the conversation.
        Raises PermissionDenied if not authorized.
        """
        if not cls.verify_membership(user, conversation):
            logger.warning(f"Access denied to conversation {conversation.id} for user {getattr(user, 'id', None)}")
            raise PermissionDenied("You are not authorized to access this conversation.")

    @classmethod
    def validate_can_send_message(cls, sender, conversation: Conversation) -> None:
        """
        Validates if the sender can send a message in the conversation.
        """
        if not sender.is_active:
            logger.warning(f"Message sending rejected: Sender {sender.id} is inactive.")
            raise ValidationError("Your account is inactive.")

        cls.validate_can_access_conversation(sender, conversation)

    @classmethod
    def validate_can_initiate_conversation(cls, buyer, seller_id: int, product_id: int = None) -> tuple[Conversation | None, User, Product | None]:
        """
        Validates if a conversation can be initiated/retrieved.
        If a conversation already exists between the buyer and seller:
          - Skip seller active status, seller role, and shop availability/active checks.
          - Returns (existing_conversation, seller, product).
        If conversation does not exist:
          - Enforces all checks (buyer role, seller active status, seller role, shop exists and is active, product is active and belongs to the seller).
          - Returns (None, seller, product).
        """
        # Validate that buyer is active and has correct role
        if not buyer.is_active:
            logger.warning(f"Conversation creation rejected: Buyer {buyer.id} is inactive.")
            raise ValidationError("Buyer account is inactive.")
        if buyer.role != 'buyer':
            logger.warning(f"Conversation creation rejected: User {buyer.id} role '{buyer.role}' is not 'buyer'.")
            raise ValidationError("Only users with the 'buyer' role can initiate conversations.")

        # Resolve seller
        try:
            seller = User.objects.get(pk=seller_id)
        except User.DoesNotExist:
            logger.warning(f"Conversation creation rejected: Seller with id {seller_id} does not exist.")
            raise ValidationError("Seller does not exist.")

        if buyer.id == seller.id:
            logger.warning(f"Conversation creation rejected: User {buyer.id} tried to message themselves.")
            raise ValidationError("You cannot start a conversation with yourself.")

        # Check if conversation already exists
        existing_conversation = Conversation.objects.filter(buyer=buyer, seller=seller).first()

        product = None
        if product_id:
            try:
                product = Product.objects.select_related('shop', 'shop__owner').get(pk=product_id)
            except Product.DoesNotExist:
                logger.warning(f"Conversation creation rejected: Product with id {product_id} does not exist.")
                raise ValidationError("Product does not exist.")

            # Validate product seller mapping
            if product.shop.owner_id != seller.id:
                logger.warning(
                    f"Conversation creation rejected: Product {product.id} shop owner "
                    f"{product.shop.owner_id} does not match selected seller {seller.id}."
                )
                raise ValidationError("This product does not belong to the selected seller.")

        if existing_conversation:
            # It's an existing conversation (previous user relation).
            # We allow it and skip active/deactivated checks for seller and shop!
            logger.info(f"Existing conversation {existing_conversation.id} found between buyer {buyer.id} and seller {seller.id}. Skipping seller/shop status checks.")
            return existing_conversation, seller, product

        # New conversation: Enforce strict seller and shop active checks
        if not seller.is_active:
            logger.warning(f"Conversation creation rejected: Seller {seller.id} is inactive.")
            raise ValidationError("Seller account is inactive.")
        if seller.role != 'seller':
            logger.warning(f"Conversation creation rejected: Selected user {seller.id} role is not 'seller'.")
            raise ValidationError("Conversations can only be initiated with sellers.")

        # Validate seller's shop availability
        try:
            shop = seller.shop
        except Exception:
            logger.warning(f"Conversation creation rejected: Seller {seller.id} has no registered shop.")
            raise ValidationError("Seller does not have a shop.")

        if not shop.is_active or shop.is_deactivated or shop.status != 'approved':
            logger.warning(
                f"Conversation creation rejected: Seller shop {shop.id} is "
                f"inactive ({not shop.is_active}), deactivated ({shop.is_deactivated}), "
                f"or not approved ({shop.status})."
            )
            raise ValidationError("This seller's shop is currently unavailable.")



        if product:
            if not product.is_active:
                logger.warning(f"Conversation creation rejected: Product {product.id} is inactive.")
                raise ValidationError("This product is inactive.")

        return None, seller, product


class IsConversationParticipant(permissions.BasePermission):
    """
    DRF permission ensuring the requesting user is either the buyer or the seller of the conversation.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not hasattr(request.user, 'id') or getattr(request.user, 'is_anonymous', False):
            return False

        # Support checking permission on Conversation directly
        if isinstance(obj, Conversation):
            return ChatPermissionValidator.verify_membership(request.user, obj)

        # Support checking permission on Message (by traversing to its conversation)
        if hasattr(obj, 'conversation') and obj.conversation:
            return ChatPermissionValidator.verify_membership(request.user, obj.conversation)

        return False

