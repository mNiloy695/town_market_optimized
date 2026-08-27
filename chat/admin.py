from django.contrib import admin
from chat.models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'seller', 'last_message_at', 'created_at')
    search_fields = ('buyer__phone', 'seller__phone', 'id')
    list_filter = ('last_message_at', 'created_at')
    ordering = ('-last_message_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'message_type', 'is_read', 'created_at')
    search_fields = ('content', 'file_name', 'id', 'sender__phone')
    list_filter = ('message_type', 'is_read', 'created_at')
    ordering = ('created_at',)
