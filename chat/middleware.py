from urllib.parse import parse_qs
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Decodes and validates the SimpleJWT token, retrieving the associated active user.
    """
    try:
        # SimpleJWT AccessToken automatically verifies signature and expiration
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
        if not user.is_active:
            logger.warning(f"Connection rejected: user {user_id} is inactive.")
            return AnonymousUser()
        return user
    except Exception as e:
        logger.debug(f"JWT signature or validation check failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections via SimpleJWT tokens.
    Supports query parameter `?token=<JWT>` or header `Authorization: Bearer <JWT>`.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token = None

        # 1. Parse token from query parameter "?token=..."
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token_list = query_params.get('token')
        if token_list:
            token = token_list[0]

        # 2. Parse token from headers if not found in query parameter
        if not token:
            headers = dict(scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode('utf-8')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        # 3. Authenticate user
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)
