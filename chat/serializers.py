from rest_framework import serializers
from django.contrib.auth import get_user_model
from chat.models import Conversation, Message
from product.models.product import Product
from chat.selectors import is_user_online

User = get_user_model()


class UserSnippetSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    shop = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'phone', 'avatar', 'shop', 'is_online', 'role']

    def get_avatar(self, obj):
        try:
            if hasattr(obj, 'profile') and obj.profile.avatar:
                request = self.context.get('request')
                avatar_url = obj.profile.avatar.url
                if request:
                    return request.build_absolute_uri(avatar_url)
                return avatar_url
        except Exception:
            pass
        return None

    def get_shop(self, obj):
        try:
            if hasattr(obj, 'shop') and obj.role == 'seller':
                shop = obj.shop
                return {
                    'id': shop.id,
                    'name': shop.name,
                    'is_active': shop.is_active,
                    'is_deactivated': shop.is_deactivated,
                    'is_open': shop.is_open,
                    'status': shop.status,
                }
        except Exception:
            pass
        return None

    def get_is_online(self, obj):
        return is_user_online(getattr(obj, 'id', None))


class ProductSnippetSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image', 'slug']

    def get_price(self, obj):
        variant = obj.variants.first()
        if variant:
            return float(variant.price)
        return 0.00

    def get_image(self, obj):
        img = obj.images.first()
        if img and img.image:
            request = self.context.get('request')
            image_url = img.image.url
            if request:
                return request.build_absolute_uri(image_url)
            return image_url
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSnippetSerializer(read_only=True)
    product = ProductSnippetSerializer(read_only=True)
    attachment_url = serializers.SerializerMethodField()
    conversation = serializers.UUIDField(source='conversation_id', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id',
            'conversation',
            'sender',
            'sender_id',
            'message_type',
            'content',
            'product',
            'file_name',
            'file_type',
            'file_size',
            'attachment_url',
            'created_at',
            'is_read',
            'read_at'
        ]

    def get_attachment_url(self, obj):
        if obj.attachment:
            request = self.context.get('request')
            path = f"/v1/chat/messages/{obj.id}/attachment/"
            if request:
                return request.build_absolute_uri(path)
            return path
        return None


class ConversationSerializer(serializers.ModelSerializer):
    participant = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'participant',
            'last_message',
            'unread_count',
            'created_at',
            'updated_at',
            'last_message_at'
        ]

    def get_participant(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return None

        try:
            other_user = obj.seller if obj.buyer_id == request.user.id else obj.buyer
        except Exception:
            return None

        if other_user is None:
            return None

        return UserSnippetSerializer(other_user, context=self.context).data

    def get_unread_count(self, obj):
        return getattr(obj, 'unread_count', 0)

    def get_last_message(self, obj):
        last_msg_id = getattr(obj, 'last_msg_id', None)
        if last_msg_id:
            return {
                'id': str(last_msg_id),
                'message_type': getattr(obj, 'last_msg_type', 'text'),
                'content': getattr(obj, 'last_msg_content', ''),
                'created_at': getattr(obj, 'last_msg_created_at', None),
            }
        
        # Fallback in case of direct model instances without selector annotation
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'id': str(last_msg.id),
                'message_type': last_msg.message_type,
                'content': last_msg.content,
                'created_at': last_msg.created_at,
            }
        return None
