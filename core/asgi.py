import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
# Initialize Django app registry early to prevent AppRegistryNotReady exceptions
django.setup()
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from chat.middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
