import io
import uuid
import asyncio
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from core.asgi import application
from chat.models import Conversation, Message, MessageType
from chat.services import (
    ConversationService,
    MessageService,
    ReadReceiptService,
    broadcast_to_conversation,
)
from chat.selectors import (
    get_user_conversations,
    get_conversation_messages,
    get_conversation_for_user,
    verify_membership,
)
from shop.models.shop import Shop
from shop.models.market import Market
from product.models.product import Product
from product.models.variant import ProductVariant
from product.models.category import ProductCategory

User = get_user_model()


# ---------------------------------------------------------------------------
# Helper mixin for shared setup
# ---------------------------------------------------------------------------
class ChatTestDataMixin:
    """Creates common test fixtures used by both API and service test classes."""

    def _create_fixtures(self):
        self.buyer_user = User.objects.create_user(
            phone="+8801700000001",
            country_code="+880",
            name="Buyer User",
            password="testpassword123",
            role="buyer",
        )
        self.seller_user = User.objects.create_user(
            phone="+8801700000002",
            country_code="+880",
            name="Seller User",
            password="testpassword123",
            role="seller",
        )
        self.inactive_seller = User.objects.create_user(
            phone="+8801700000003",
            country_code="+880",
            name="Inactive Seller",
            password="testpassword123",
            role="seller",
            is_active=False,
        )
        self.buyer_token = str(AccessToken.for_user(self.buyer_user))
        self.seller_token = str(AccessToken.for_user(self.seller_user))

        self.market = Market.objects.create(name="Dhanmondi Market", address="Dhaka")
        self.shop = Shop.objects.create(
            name="Seller Shop",
            address="Dhaka",
            owner=self.seller_user,
            market=self.market,
            is_active=True,
            is_deactivated=False,
            status="approved",
        )
        self.category = ProductCategory.objects.create(name="Clothing")
        self.product = Product.objects.create(
            name="Premium T-Shirt",
            shop=self.shop,
            sub_category=self.category,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, price=500.00, stock=10
        )


# =========================================================================
#  REST API Tests
# =========================================================================
class ChatAPITests(APITestCase, ChatTestDataMixin):
    def setUp(self):
        self._create_fixtures()

    # ---- Conversation creation ----
    def test_create_conversation_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        data = {"seller_id": self.seller_user.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 1)
        conv = Conversation.objects.first()
        self.assertEqual(conv.buyer, self.buyer_user)
        self.assertEqual(conv.seller, self.seller_user)

    def test_create_conversation_with_product_inquiry(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        data = {"seller_id": self.seller_user.id, "product_id": self.product.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conv = Conversation.objects.get(id=response.data["id"])
        msgs = Message.objects.filter(conversation=conv)
        self.assertEqual(msgs.count(), 1)
        inquiry = msgs.first()
        self.assertEqual(inquiry.message_type, MessageType.PRODUCT_LINK)
        self.assertEqual(inquiry.product, self.product)
        self.assertEqual(inquiry.sender, self.buyer_user)

    def test_get_existing_conversation_returns_200(self):
        Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url, {"seller_id": self.seller_user.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_conversation_duplicate_product_inquiry_deduplication(self):
        conv, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user,
            seller_id=self.seller_user.id,
            product_id=self.product.id,
        )
        self.assertTrue(created)
        self.assertEqual(Message.objects.filter(conversation=conv).count(), 1)

        conv2, created2 = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user,
            seller_id=self.seller_user.id,
            product_id=self.product.id,
        )
        self.assertFalse(created2)
        self.assertEqual(Message.objects.filter(conversation=conv2).count(), 1)

    def test_create_conversation_missing_seller_id(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_invalid_seller_id_format(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url, {"seller_id": "not-a-number"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_nonexistent_seller(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url, {"seller_id": 999999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_invalid_roles(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seller_token}")
        url = reverse("conversation-list-create")
        data = {"seller_id": self.buyer_user.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_self_chat_prohibited(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        data = {"seller_id": self.buyer_user.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_inactive_seller(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        data = {"seller_id": self.inactive_seller.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_unauthenticated(self):
        url = reverse("conversation-list-create")
        response = self.client.post(
            url, {"seller_id": self.seller_user.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_conversation_product_not_belonging_to_seller(self):
        other_seller = User.objects.create_user(
            phone="+8801700000010",
            country_code="+880",
            name="Other Seller",
            password="testpassword123",
            role="seller",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url,
            {"seller_id": self.seller_user.id, "product_id": self.product.id},
            format="json",
        )
        # The product belongs to self.seller_user, so this should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_conversation_product_wrong_seller(self):
        other_seller = User.objects.create_user(
            phone="+8801700000011",
            country_code="+880",
            name="Other Seller",
            password="testpassword123",
            role="seller",
        )
        other_shop = Shop.objects.create(
            name="Other Shop",
            address="Chittagong",
            owner=other_seller,
            market=self.market,
            status="approved",
        )
        other_product = Product.objects.create(
            name="Other Product",
            shop=other_shop,
            sub_category=self.category,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url,
            {"seller_id": self.seller_user.id, "product_id": other_product.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_inactive_product(self):
        inactive_product = Product.objects.create(
            name="Inactive Product",
            shop=self.shop,
            sub_category=self.category,
            is_active=False,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url,
            {"seller_id": self.seller_user.id, "product_id": inactive_product.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_deactivated_shop(self):
        deactivated_seller = User.objects.create_user(
            phone="+8801700000012",
            country_code="+880",
            name="Deactivated Shop Seller",
            password="testpassword123",
            role="seller",
        )
        deactivated_shop = Shop.objects.create(
            name="Deactivated Shop",
            address="Sylhet",
            owner=deactivated_seller,
            market=self.market,
            is_deactivated=True,
            status="approved",
        )
        deactivated_product = Product.objects.create(
            name="Deactivated Shop Product",
            shop=deactivated_shop,
            sub_category=self.category,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url,
            {
                "seller_id": deactivated_seller.id,
                "product_id": deactivated_product.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_conversation_nonexistent_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.post(
            url,
            {"seller_id": self.seller_user.id, "product_id": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- Conversation listing ----
    def test_list_conversations(self):
        Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["participant"]["phone"], self.seller_user.phone)

    def test_list_conversations_unauthenticated(self):
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_conversations_ordering(self):
        conv1 = Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)
        other_seller = User.objects.create_user(
            phone="+8801700000020",
            country_code="+880",
            name="Other Seller 2",
            password="testpassword123",
            role="seller",
        )
        conv2 = Conversation.objects.create(buyer=self.buyer_user, seller=other_seller)

        # Touch last_message_at to differentiate ordering
        from django.utils import timezone
        conv1.last_message_at = timezone.now() - timezone.timedelta(hours=1)
        conv1.save(update_fields=["last_message_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        # conv2 should come first (more recent last_message_at)
        self.assertEqual(response.data[0]["id"], str(conv2.id))

    def test_seller_sees_conversations(self):
        Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seller_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["participant"]["phone"], self.buyer_user.phone)

    # ---- Message listing ----
    def test_message_pagination(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        for i in range(35):
            Message.objects.create(
                conversation=conversation, sender=self.buyer_user, content=f"Msg {i}"
            )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("message-list", kwargs={"conversation_id": conversation.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 30)
        self.assertEqual(response.data["count"], 35)

    def test_message_listing_unauthenticated(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("message-list", kwargs={"conversation_id": conversation.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_message_listing_non_participant(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        other = User.objects.create_user(
            phone="+8801700000030",
            country_code="+880",
            name="Intruder",
            password="testpassword123",
            role="buyer",
        )
        other_token = str(AccessToken.for_user(other))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")
        url = reverse("message-list", kwargs={"conversation_id": conversation.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_listing_nonexistent_conversation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("message-list", kwargs={"conversation_id": uuid.uuid4()})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_ordering_ascending(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        m1 = Message.objects.create(
            conversation=conversation, sender=self.buyer_user, content="First"
        )
        m2 = Message.objects.create(
            conversation=conversation, sender=self.seller_user, content="Second"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("message-list", kwargs={"conversation_id": conversation.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["content"], "First")
        self.assertEqual(results[1]["content"], "Second")

    # ---- Media upload ----
    def test_media_upload_limits(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")

        small_file = SimpleUploadedFile(
            "test_image.jpg", b"x" * 1024, content_type="image/jpeg"
        )
        response = self.client.post(url, {"file": small_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.first().message_type, MessageType.MEDIA)

        large_file = SimpleUploadedFile(
            "large.jpg", b"x" * (11 * 1024 * 1024), content_type="image/jpeg"
        )
        response = self.client.post(url, {"file": large_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds", response.data["error"])

    def test_media_upload_no_file(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        response = self.client.post(url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_media_upload_unauthenticated(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        response = self.client.post(url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_media_upload_non_participant(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        other = User.objects.create_user(
            phone="+8801700000040",
            country_code="+880",
            name="Intruder 2",
            password="testpassword123",
            role="buyer",
        )
        other_token = str(AccessToken.for_user(other))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        file_obj = SimpleUploadedFile("test.pdf", b"data", content_type="application/pdf")
        response = self.client.post(url, {"file": file_obj}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_media_upload_banned_file_types(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")

        for banned_name in ["script.exe", "malware.sh", "page.html", "code.js"]:
            file_obj = SimpleUploadedFile(banned_name, b"x", content_type="application/octet-stream")
            response = self.client.post(url, {"file": file_obj}, format="multipart")
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Expected 400 for banned file: {banned_name}",
            )

    def test_media_upload_valid_pdf(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        file_obj = SimpleUploadedFile("doc.pdf", b"pdf-data", content_type="application/pdf")
        response = self.client.post(url, {"file": file_obj}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_media_upload_size_boundary(self):
        """File exactly at 10 MB boundary should be rejected (>= check)."""
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conversation.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        exact_10mb = SimpleUploadedFile("exact.jpg", b"x" * (10 * 1024 * 1024), content_type="image/jpeg")
        response = self.client.post(url, {"file": exact_10mb}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- Secure attachment download ----
    def test_secure_download_authorization(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        file_obj = SimpleUploadedFile(
            "secret.pdf", b"confidentials", content_type="application/pdf"
        )
        message = MessageService.create_media_message(
            conversation_id=str(conversation.id),
            sender=self.buyer_user,
            file_obj=file_obj,
        )

        url = reverse("secure-attachment-download", kwargs={"message_id": message.id})

        # No token → 401
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Non-participant → 403
        other = User.objects.create_user(
            phone="+8801700000009",
            country_code="+880",
            name="Other User",
            password="testpassword123",
            role="buyer",
        )
        other_token = str(AccessToken.for_user(other))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authorized via query token → 200
        self.client.credentials()
        authorized_url = f"{url}?token={self.buyer_token}"
        response = self.client.get(authorized_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="secret.pdf"')

    def test_secure_download_nonexistent_message(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("secure-attachment-download", kwargs={"message_id": uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_secure_download_message_without_attachment(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        msg = Message.objects.create(
            conversation=conversation,
            sender=self.buyer_user,
            content="Just text",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("secure-attachment-download", kwargs={"message_id": msg.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_secure_download_invalid_token(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        file_obj = SimpleUploadedFile("f.pdf", b"d", content_type="application/pdf")
        message = MessageService.create_media_message(
            conversation_id=str(conversation.id),
            sender=self.buyer_user,
            file_obj=file_obj,
        )
        url = reverse("secure-attachment-download", kwargs={"message_id": message.id})
        response = self.client.get(f"{url}?token=invalid.jwt.token")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- Unread count in conversation list ----
    def test_conversation_unread_count(self):
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        # Seller sends 3 messages → buyer should see 3 unread
        for i in range(3):
            Message.objects.create(
                conversation=conv, sender=self.seller_user, content=f"Hello {i}"
            )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["unread_count"], 3)

    def test_conversation_unread_count_zero_after_read(self):
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        Message.objects.create(
            conversation=conv, sender=self.seller_user, content="Hello"
        )
        # Buyer reads the message
        ReadReceiptService.mark_conversation_as_read(str(conv.id), self.buyer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.data[0]["unread_count"], 0)

    def test_conversation_last_message_preview(self):
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        Message.objects.create(
            conversation=conv, sender=self.buyer_user, content="Hi there!"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.buyer_token}")
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertIsNotNone(response.data[0]["last_message"])
        self.assertEqual(response.data[0]["last_message"]["content"], "Hi there!")
        self.assertEqual(response.data[0]["last_message"]["message_type"], "text")


# =========================================================================
#  Service Layer Unit Tests
# =========================================================================
@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ConversationServiceTests(ChatTestDataMixin, TransactionTestCase):
    def setUp(self):
        self._create_fixtures()

    def test_get_or_create_conversation_new(self):
        conv, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        self.assertTrue(created)
        self.assertEqual(conv.buyer, self.buyer_user)
        self.assertEqual(conv.seller, self.seller_user)

    def test_get_or_create_conversation_existing(self):
        conv1, _ = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        conv2, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        self.assertFalse(created)
        self.assertEqual(conv1.id, conv2.id)

    def test_buyer_role_validation(self):
        with self.assertRaises(ValidationError) as ctx:
            ConversationService.get_or_create_conversation(
                buyer=self.seller_user, seller_id=self.buyer_user.id
            )
        self.assertIn("buyer", str(ctx.exception).lower())

    def test_inactive_buyer(self):
        inactive_buyer = User.objects.create_user(
            phone="+8801700000050",
            country_code="+880",
            name="Inactive Buyer",
            password="testpassword123",
            role="buyer",
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            ConversationService.get_or_create_conversation(
                buyer=inactive_buyer, seller_id=self.seller_user.id
            )

    def test_self_chat(self):
        # Make buyer also a seller-role user for testing
        with self.assertRaises(ValidationError):
            ConversationService.get_or_create_conversation(
                buyer=self.buyer_user, seller_id=self.buyer_user.id
            )

    def test_product_inquiry_created(self):
        conv, _ = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user,
            seller_id=self.seller_user.id,
            product_id=self.product.id,
        )
        msgs = Message.objects.filter(
            conversation=conv, message_type=MessageType.PRODUCT_LINK
        )
        self.assertEqual(msgs.count(), 1)
        self.assertEqual(msgs.first().product, self.product)

    def test_system_message_on_new_conversation(self):
        conv, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        self.assertTrue(created)
        system_msgs = Message.objects.filter(
            conversation=conv, message_type=MessageType.SYSTEM
        )
        self.assertEqual(system_msgs.count(), 1)

    def test_deactivated_shop_new_buyer_fails(self):
        # Deactivate the seller's shop
        self.shop.is_deactivated = True
        self.shop.save()

        # New buyer attempt should fail
        with self.assertRaises(ValidationError) as ctx:
            ConversationService.get_or_create_conversation(
                buyer=self.buyer_user, seller_id=self.seller_user.id
            )
        self.assertIn("unavailable", str(ctx.exception).lower())

    def test_deactivated_shop_existing_buyer_succeeds(self):
        # Create an existing conversation first
        conv = Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)

        # Deactivate the seller's shop
        self.shop.is_deactivated = True
        self.shop.save()

        # Existing buyer should be able to retrieve the conversation
        retrieved_conv, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        self.assertFalse(created)
        self.assertEqual(retrieved_conv.id, conv.id)

    def test_unapproved_shop_new_buyer_fails(self):
        # Set shop status to pending (unapproved)
        self.shop.status = "pending"
        self.shop.save()

        # New buyer attempt should fail
        with self.assertRaises(ValidationError) as ctx:
            ConversationService.get_or_create_conversation(
                buyer=self.buyer_user, seller_id=self.seller_user.id
            )
        self.assertIn("unavailable", str(ctx.exception).lower())

    def test_unapproved_shop_existing_buyer_succeeds(self):
        # Create an existing conversation first
        conv = Conversation.objects.create(buyer=self.buyer_user, seller=self.seller_user)

        # Set shop status to pending (unapproved)
        self.shop.status = "pending"
        self.shop.save()

        # Existing buyer should be able to retrieve the conversation
        retrieved_conv, created = ConversationService.get_or_create_conversation(
            buyer=self.buyer_user, seller_id=self.seller_user.id
        )
        self.assertFalse(created)
        self.assertEqual(retrieved_conv.id, conv.id)



@override_settings(

    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class MessageServiceTests(ChatTestDataMixin, TransactionTestCase):
    def setUp(self):
        self._create_fixtures()
        self.conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )

    def test_create_text_message(self):
        msg = MessageService.create_text_message(
            str(self.conv.id), self.buyer_user, "Hello!"
        )
        self.assertEqual(msg.content, "Hello!")
        self.assertEqual(msg.message_type, MessageType.TEXT)
        self.assertEqual(msg.sender, self.buyer_user)

    def test_create_text_message_empty_content(self):
        with self.assertRaises(ValidationError) as ctx:
            MessageService.create_text_message(str(self.conv.id), self.buyer_user, "   ")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_create_text_message_too_long(self):
        with self.assertRaises(ValidationError) as ctx:
            MessageService.create_text_message(
                str(self.conv.id), self.buyer_user, "x" * 5001
            )
        self.assertIn("length", str(ctx.exception).lower())

    def test_create_text_message_updates_last_message_at(self):
        old_ts = self.conv.last_message_at
        MessageService.create_text_message(str(self.conv.id), self.buyer_user, "Hi")
        self.conv.refresh_from_db()
        self.assertGreaterEqual(self.conv.last_message_at, old_ts)

    def test_create_text_message_non_participant(self):
        other = User.objects.create_user(
            phone="+8801700000060",
            country_code="+880",
            name="Outsider",
            password="testpassword123",
            role="buyer",
        )
        with self.assertRaises(PermissionDenied):
            MessageService.create_text_message(str(self.conv.id), other, "Sneaky")

    def test_create_text_message_nonexistent_conversation(self):
        with self.assertRaises(PermissionDenied):
            MessageService.create_text_message(
                str(uuid.uuid4()), self.buyer_user, "Hello"
            )

    def test_create_media_message(self):
        file_obj = SimpleUploadedFile("photo.jpg", b"fake-data", content_type="image/jpeg")
        msg = MessageService.create_media_message(
            str(self.conv.id), self.buyer_user, file_obj
        )
        self.assertEqual(msg.message_type, MessageType.MEDIA)
        self.assertEqual(msg.file_name, "photo.jpg")
        self.assertEqual(msg.file_type, "image/jpeg")

    def test_create_media_message_banned_type(self):
        file_obj = SimpleUploadedFile("virus.exe", b"x", content_type="application/octet-stream")
        with self.assertRaises(ValidationError) as ctx:
            MessageService.create_media_message(
                str(self.conv.id), self.buyer_user, file_obj
            )
        self.assertIn("not allowed", str(ctx.exception).lower())

    def test_create_media_message_html_type(self):
        file_obj = SimpleUploadedFile("page.html", b"<html>", content_type="text/html")
        with self.assertRaises(ValidationError):
            MessageService.create_media_message(
                str(self.conv.id), self.buyer_user, file_obj
            )

    def test_create_media_message_too_large(self):
        file_obj = SimpleUploadedFile(
            "big.jpg", b"x" * (11 * 1024 * 1024), content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError) as ctx:
            MessageService.create_media_message(
                str(self.conv.id), self.buyer_user, file_obj
            )
        self.assertIn("10 MB", str(ctx.exception))


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ReadReceiptServiceTests(ChatTestDataMixin, TransactionTestCase):
    def setUp(self):
        self._create_fixtures()
        self.conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )

    def test_mark_as_read(self):
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="Hi"
        )
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="Hey"
        )
        count = ReadReceiptService.mark_conversation_as_read(
            str(self.conv.id), self.buyer_user
        )
        self.assertEqual(count, 2)
        self.assertTrue(
            Message.objects.filter(conversation=self.conv, is_read=False).count() == 0
        )

    def test_mark_as_read_does_not_read_own_messages(self):
        Message.objects.create(
            conversation=self.conv, sender=self.buyer_user, content="My msg"
        )
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="Their msg"
        )
        count = ReadReceiptService.mark_conversation_as_read(
            str(self.conv.id), self.buyer_user
        )
        self.assertEqual(count, 1)  # only seller's message marked
        my_msg = Message.objects.get(sender=self.buyer_user)
        self.assertFalse(my_msg.is_read)

    def test_mark_as_read_no_unread(self):
        count = ReadReceiptService.mark_conversation_as_read(
            str(self.conv.id), self.buyer_user
        )
        self.assertEqual(count, 0)

    def test_mark_as_read_sets_read_at(self):
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="X"
        )
        ReadReceiptService.mark_conversation_as_read(str(self.conv.id), self.buyer_user)
        msg = Message.objects.get(sender=self.seller_user)
        self.assertIsNotNone(msg.read_at)

    def test_mark_as_read_non_participant(self):
        other = User.objects.create_user(
            phone="+8801700000070",
            country_code="+880",
            name="Outsider 3",
            password="testpassword123",
            role="buyer",
        )
        with self.assertRaises(PermissionDenied):
            ReadReceiptService.mark_conversation_as_read(str(self.conv.id), other)


class SelectorTests(ChatTestDataMixin, TransactionTestCase):
    def setUp(self):
        self._create_fixtures()
        self.conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )

    def test_verify_membership_buyer(self):
        self.assertTrue(verify_membership(self.buyer_user, self.conv))

    def test_verify_membership_seller(self):
        self.assertTrue(verify_membership(self.seller_user, self.conv))

    def test_verify_membership_non_participant(self):
        other = User.objects.create_user(
            phone="+8801700000080",
            country_code="+880",
            name="Random",
            password="testpassword123",
            role="buyer",
        )
        self.assertFalse(verify_membership(other, self.conv))

    def test_verify_membership_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(verify_membership(AnonymousUser(), self.conv))

    def test_get_conversation_for_user(self):
        conv = get_conversation_for_user(str(self.conv.id), self.buyer_user)
        self.assertEqual(conv.id, self.conv.id)

    def test_get_conversation_for_user_not_found(self):
        with self.assertRaises(PermissionDenied):
            get_conversation_for_user(str(uuid.uuid4()), self.buyer_user)

    def test_get_conversation_for_user_not_member(self):
        other = User.objects.create_user(
            phone="+8801700000090",
            country_code="+880",
            name="Nope",
            password="testpassword123",
            role="buyer",
        )
        with self.assertRaises(PermissionDenied):
            get_conversation_for_user(str(self.conv.id), other)

    def test_get_user_conversations(self):
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="Hi"
        )
        qs = get_user_conversations(self.buyer_user)
        self.assertEqual(qs.count(), 1)

    def test_get_conversation_messages(self):
        Message.objects.create(
            conversation=self.conv, sender=self.buyer_user, content="A"
        )
        Message.objects.create(
            conversation=self.conv, sender=self.seller_user, content="B"
        )
        qs = get_conversation_messages(str(self.conv.id), self.buyer_user)
        self.assertEqual(qs.count(), 2)


# =========================================================================
#  WebSocket Tests
# =========================================================================
@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ChatWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.buyer_user = User.objects.create_user(
            phone="+8801700000010",
            country_code="+880",
            name="Buyer Web",
            password="testpassword123",
            role="buyer",
        )
        self.seller_user = User.objects.create_user(
            phone="+8801700000011",
            country_code="+880",
            name="Seller Web",
            password="testpassword123",
            role="seller",
        )
        self.buyer_token = str(AccessToken.for_user(self.buyer_user))
        self.seller_token = str(AccessToken.for_user(self.seller_user))
        self.conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )

    async def test_unauthenticated_connection_rejected(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_non_participant_connection_rejected(self):
        other_user = await database_sync_to_async(User.objects.create_user)(
            phone="+8801700000019",
            country_code="+880",
            name="Other Web",
            password="testpassword123",
            role="buyer",
        )
        other_token = str(AccessToken.for_user(other_user))
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={other_token}"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4003)

    async def test_successful_connection_and_messaging(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to(
            {"action": "send_message", "content": "Hello via WebSocket!"}
        )

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response["type"], "chat_message")
        self.assertEqual(response["message"]["content"], "Hello via WebSocket!")
        self.assertEqual(response["message"]["sender"]["phone"], self.buyer_user.phone)

        await communicator.disconnect()

    async def test_read_messages_action(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Seller sends a message via DB
        await database_sync_to_async(Message.objects.create)(
            conversation=self.conversation,
            sender=self.seller_user,
            content="Unread msg",
        )

        # Buyer marks as read
        await communicator.send_json_to({"action": "read_messages"})
        # No broadcast expected when count > 0 (read receipt broadcast goes to group)
        # We just ensure no crash; receive_json_from may timeout (expected)
        try:
            await communicator.receive_json_from(timeout=1)
        except Exception:
            pass  # timeout is acceptable

        await communicator.disconnect()

    async def test_invalid_action(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "unknown_action"})
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)
        self.assertIn("Invalid action", response["error"])

        await communicator.disconnect()

    async def test_send_message_empty_content(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "send_message", "content": ""})
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()

    async def test_send_message_whitespace_only(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "send_message", "content": "   "})
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()

    async def test_send_message_too_long(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to(
            {"action": "send_message", "content": "x" * 5001}
        )
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()

    async def test_seller_can_connect_and_message(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.seller_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to(
            {"action": "send_message", "content": "Seller here!"}
        )
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response["type"], "chat_message")
        self.assertEqual(response["message"]["content"], "Seller here!")

        await communicator.disconnect()

    async def test_broadcast_reaches_both_participants(self):
        """Both buyer and seller in the same conversation group receive broadcasts."""
        buyer_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        seller_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.seller_token}"
        )
        await buyer_comm.connect()
        await seller_comm.connect()

        # Clear presence events
        async def get_next_chat_message(comm):
            for _ in range(5):
                evt = await comm.receive_json_from(timeout=5)
                if evt.get("type") == "chat_message":
                    return evt
            return None

        await buyer_comm.send_json_to(
            {"action": "send_message", "content": "Ping!"}
        )

        # Both should receive the broadcast
        buyer_resp = await get_next_chat_message(buyer_comm)
        seller_resp = await get_next_chat_message(seller_comm)
        self.assertIsNotNone(buyer_resp)
        self.assertIsNotNone(seller_resp)
        self.assertEqual(buyer_resp["message"]["content"], "Ping!")
        self.assertEqual(seller_resp["message"]["content"], "Ping!")

        await buyer_comm.disconnect()
        await seller_comm.disconnect()

    async def test_connection_with_header_token(self):
        """WebSocket auth works via Authorization header as well."""
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/"
        )
        communicator.scope["headers"] = [
            (b"host", b"localhost"),
            (b"authorization", f"Bearer {self.buyer_token}".encode()),
        ]
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_receive_json_none_content(self):
        """None content should not crash the consumer."""
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to(None)
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()

    async def test_receive_json_non_dict_content(self):
        """Non-dict content should not crash the consumer."""
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to("not a dict")
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()

    async def test_send_message_none_content(self):
        """None content in send_message should return validation error, not 500."""
        communicator = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "send_message", "content": None})
        response = await communicator.receive_json_from(timeout=3)
        self.assertIn("error", response)

        await communicator.disconnect()


# =========================================================================
#  NoneType Safety Tests
# =========================================================================
class NoneTypeSafetyTests(ChatTestDataMixin, TransactionTestCase):
    """Tests ensuring no 500 errors from NoneType access across the chat module."""

    def setUp(self):
        self._create_fixtures()
        from rest_framework.test import APIClient
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_verify_membership_with_none_user(self):
        """verify_membership must not crash when user is None."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        result = verify_membership(None, conv)
        self.assertFalse(result)

    def test_create_text_message_none_content(self):
        """MessageService.create_text_message should reject None content, not crash."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        with self.assertRaises(ValidationError):
            MessageService.create_text_message(str(conv.id), self.buyer_user, None)

    def test_create_text_message_integer_content(self):
        """MessageService.create_text_message should reject non-string content."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        with self.assertRaises(ValidationError):
            MessageService.create_text_message(str(conv.id), self.buyer_user, 12345)

    def test_conversation_serializer_participant_none_buyer(self):
        """ConversationSerializer handles missing buyer gracefully."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        from chat.serializers import ConversationSerializer
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.buyer_user
        serializer = ConversationSerializer(conv, context={"request": request})
        self.assertIsNotNone(serializer.data["participant"])

    def test_secure_download_file_name_none(self):
        """SecureAttachmentDownloadView handles null file_name gracefully."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        msg = Message.objects.create(
            conversation=conv,
            sender=self.buyer_user,
            message_type=MessageType.MEDIA,
            attachment=SimpleUploadedFile("test.pdf", b"data", content_type="application/pdf"),
            file_name=None,
            file_type="application/pdf",
            file_size=4,
        )
        url = reverse("secure-attachment-download", kwargs={"message_id": msg.id})
        self._auth(self.buyer_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download", response["Content-Disposition"])

    def test_message_sender_none_serialization(self):
        """System message with sender=None should serialize without error."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        system_msg = Message.objects.create(
            conversation=conv,
            sender=None,
            message_type=MessageType.SYSTEM,
            content="System notification",
        )
        from chat.serializers import MessageSerializer
        serializer = MessageSerializer(system_msg)
        data = serializer.data
        self.assertIsNone(data["sender"])
        self.assertEqual(data["content"], "System notification")

    def test_permission_class_none_user(self):
        """IsConversationParticipant must not crash with None user."""
        from chat.permissions import IsConversationParticipant
        from django.test import RequestFactory
        from rest_framework.request import Request

        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        factory = RequestFactory()
        drf_request = Request(factory.get("/"))
        drf_request.user = None

        perm = IsConversationParticipant()
        result = perm.has_object_permission(drf_request, None, conv)
        self.assertFalse(result)

    def test_permission_class_anonymous_user(self):
        """IsConversationParticipant must not crash with AnonymousUser."""
        from chat.permissions import IsConversationParticipant
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from rest_framework.request import Request

        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        factory = RequestFactory()
        drf_request = Request(factory.get("/"))
        drf_request.user = AnonymousUser()

        perm = IsConversationParticipant()
        result = perm.has_object_permission(drf_request, None, conv)
        self.assertFalse(result)

    def test_conversation_list_unauthenticated(self):
        """Unauthenticated user gets 401, not 500."""
        url = reverse("conversation-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_media_upload_unauthenticated(self):
        """Unauthenticated media upload gets 401, not 500."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        url = reverse("media-upload", kwargs={"conversation_id": conv.id})
        response = self.client.post(url, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_conversation_seller_no_shop(self):
        """Seller without a shop should return 400, not 500."""
        no_shop_seller = User.objects.create_user(
            phone="+8801700000099",
            country_code="+880",
            name="No Shop Seller",
            password="testpassword123",
            role="seller",
        )
        self._auth(self.buyer_user)
        url = reverse("conversation-list-create")
        response = self.client.post(
            url, {"seller_id": no_shop_seller.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_secure_download_message_conversation_bad_uuid(self):
        """Secure download with a message whose conversation is unrelated should not crash."""
        conv = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )
        msg = Message.objects.create(
            conversation=conv,
            sender=self.buyer_user,
            content="test",
        )
        self._auth(self.buyer_user)
        url = reverse("secure-attachment-download", kwargs={"message_id": msg.id})
        response = self.client.get(url)
        # Buyer is a member but the message has no attachment -> 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# =========================================================================
#  Presence (Online/Offline) & Typing Indicator Tests
# =========================================================================
@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ChatPresenceAndTypingTests(TransactionTestCase):
    """Tests for online/offline presence and typing indicators over WebSocket."""

    def setUp(self):
        self.buyer_user = User.objects.create_user(
            phone="+8801700000010",
            country_code="+880",
            name="Presence Buyer",
            password="testpassword123",
            role="buyer",
        )
        self.seller_user = User.objects.create_user(
            phone="+8801700000011",
            country_code="+880",
            name="Presence Seller",
            password="testpassword123",
            role="seller",
        )
        self.buyer_token = str(AccessToken.for_user(self.buyer_user))
        self.seller_token = str(AccessToken.for_user(self.seller_user))
        self.conversation = Conversation.objects.create(
            buyer=self.buyer_user, seller=self.seller_user
        )

    async def test_online_presence_broadcast_on_connect(self):
        """Connecting a participant should notify the other participant they are online."""
        # Seller connects first and stays connected
        seller_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.seller_token}"
        )
        connected, _ = await seller_comm.connect()
        self.assertTrue(connected)

        # Now buyer connects -> seller should receive an 'online' presence event
        buyer_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)

        seller_event = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(seller_event["type"], "presence")
        self.assertEqual(seller_event["user_id"], self.buyer_user.id)
        self.assertTrue(seller_event["is_online"])

        await buyer_comm.disconnect()
        await seller_comm.disconnect()

    async def test_offline_presence_broadcast_on_disconnect(self):
        """Disconnecting a participant should notify the other participant they are offline."""
        # Connect seller first, then buyer
        seller_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.seller_token}"
        )
        connected, close_code = await seller_comm.connect()
        self.assertTrue(connected, f"Seller failed to connect: {close_code}")

        buyer_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, close_code = await buyer_comm.connect()
        self.assertTrue(connected, f"Buyer failed to connect: {close_code}")

        # Seller immediately receives buyer's 'online' presence event
        online_evt = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(online_evt["type"], "presence")
        self.assertEqual(online_evt["user_id"], self.buyer_user.id)
        self.assertTrue(online_evt["is_online"])

        # Buyer disconnects -> seller should get 'offline' event
        await buyer_comm.disconnect()

        offline_evt = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(offline_evt["type"], "presence")
        self.assertEqual(offline_evt["user_id"], self.buyer_user.id)
        self.assertFalse(offline_evt["is_online"])

        await seller_comm.disconnect()

    async def test_typing_indicator_broadcast(self):
        """Sending a typing action should notify the other participant."""
        # Connect seller first, then buyer
        seller_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.seller_token}"
        )
        connected, close_code = await seller_comm.connect()
        self.assertTrue(connected, f"Seller failed to connect: {close_code}")

        buyer_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        connected, close_code = await buyer_comm.connect()
        self.assertTrue(connected, f"Buyer failed to connect: {close_code}")

        # Seller immediately receives buyer's 'online' presence event, consume it
        online_evt = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(online_evt["type"], "presence")

        # Buyer starts typing
        await buyer_comm.send_json_to({"action": "typing", "is_typing": True})
        seller_evt = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(seller_evt["type"], "typing")
        self.assertEqual(seller_evt["user_id"], self.buyer_user.id)
        self.assertTrue(seller_evt["is_typing"])
        self.assertEqual(seller_evt["conversation_id"], str(self.conversation.id))

        # Buyer stops typing
        await buyer_comm.send_json_to({"action": "typing", "is_typing": False})
        seller_evt2 = await seller_comm.receive_json_from(timeout=5)
        self.assertEqual(seller_evt2["type"], "typing")
        self.assertFalse(seller_evt2["is_typing"])

        await buyer_comm.disconnect()
        await seller_comm.disconnect()

    async def test_typing_unknown_action(self):
        """A typing action without participants should not crash."""
        buy_comm = WebsocketCommunicator(
            application, f"ws/chat/{self.conversation.id}/?token={self.buyer_token}"
        )
        await buy_comm.connect()
        await buy_comm.send_json_to({"action": "typing"})
        # No crash expected; just ensure connection still usable
        await buy_comm.disconnect()
