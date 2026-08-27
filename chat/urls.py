from django.urls import path
from chat import views

urlpatterns = [
    path('conversations/', views.ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('conversations/<uuid:conversation_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('conversations/<uuid:conversation_id>/messages/media/', views.MediaUploadView.as_view(), name='media-upload'),
    path('messages/<uuid:message_id>/attachment/', views.SecureAttachmentDownloadView.as_view(), name='secure-attachment-download'),
]
