# Senior Backend Engineering Task: Production-Grade Buyer–Seller Real-Time Chat

You are a **Senior/Staff Django Backend Engineer** responsible for implementing a production-grade buyer–seller communication system for the existing Town Market e-commerce platform.

The implementation must follow architecture and security patterns comparable to mature e-commerce marketplaces such as **Daraz, Amazon Marketplace, Alibaba, and similar platforms**.

Do not implement this as a basic Django chat tutorial. Treat it as a **high-concurrency, security-sensitive marketplace communication subsystem** that must integrate cleanly with the existing REST API, authentication, product, user, media, and infrastructure architecture.

---

## 1. Primary Objective

Implement a real-time buyer–seller messaging system using:

* Django
* Django REST Framework
* Django Channels
* `channels-redis==4.2.1`
* Redis
* WebSockets
* SimpleJWT
* PostgreSQL/SQLite-compatible Django ORM
* Existing CustomUser/User roles
* Existing Product model
* Existing media/storage infrastructure

The system must support:

1. Buyer → Seller conversations
2. Real-time text messaging
3. Secure media sharing
4. Product inquiry context
5. Message read/unread state
6. Conversation listing
7. Pagination
8. WebSocket authentication
9. Participant-level authorization
10. Secure attachment access
11. Redis-backed channel groups
12. Concurrent message handling
13. Idempotent operations where appropriate
14. Database transaction safety
15. Proper indexing
16. Security auditing
17. Automated tests
18. Production-ready frontend integration documentation

---

# 2. First Requirement: Audit Existing Project

Before modifying anything, inspect the existing project thoroughly.

Analyze:

* Django settings
* `core/asgi.py`
* `core/settings.py`
* `core/config.py`
* `core/urls.py`
* authentication implementation
* SimpleJWT configuration
* CustomUser model
* buyer/seller role implementation
* Product model
* product serializer
* product image/media fields
* existing storage configuration
* Redis configuration
* Docker Compose
* Celery configuration
* existing API versioning
* permission classes
* exception handling
* pagination
* existing test architecture
* existing naming conventions
* existing UUID patterns
* existing timestamp/timezone handling

Do **not** blindly create duplicate infrastructure.

Reuse existing project abstractions wherever appropriate.

Before implementing, determine:

* exact user role field names
* exact product model path
* exact product image field
* exact price field
* exact avatar field
* exact authentication configuration
* existing Redis service name
* existing storage backend
* existing API response format
* existing permission conventions

The implementation must fit the existing codebase rather than introducing an unrelated architecture.

---

# 3. Architectural Decision: Conversation Model

Use a generic direct buyer-seller conversation.

A conversation represents exactly one buyer ↔ seller relationship.

Recommended model:

```text
Conversation
├── id UUID
├── buyer FK CustomUser
├── seller FK CustomUser
├── created_at
├── updated_at
└── last_message_at
```

Database constraint:

```text
UNIQUE(buyer, seller)
```

Add appropriate indexes for:

```text
buyer
seller
last_message_at
```

### Important

Do not create separate conversations for every product.

A buyer asking about:

* Product A
* Product B
* Product C

from the same seller should normally remain inside the same buyer-seller conversation.

Product context belongs to individual messages.

This provides a marketplace-style persistent communication thread.

---

# 4. Conversation Semantics

The conversation must always have:

```text
buyer != seller
```

The API must reject:

* buyer chatting with themselves
* seller acting as buyer
* invalid user roles
* inactive/banned users where existing business rules require restriction

Do not trust the frontend to determine buyer/seller roles.

All role validation must happen server-side.

---

# 5. Message Model

Create a production-ready Message model.

Recommended structure:

```text
Message
├── id UUID
├── conversation FK
├── sender FK nullable
├── message_type
├── content
├── product FK nullable
├── attachment
├── file_name
├── file_type
├── file_size
├── created_at
├── updated_at
├── is_read
└── read_at
```

Supported message types:

```text
text
media
product_link
system
```

Use Django choices/enums rather than arbitrary strings.

---

# 6. System Messages

System messages must not belong to a human sender.

Examples:

```text
Product inquiry started
Order reference added
Conversation created
```

Therefore:

```text
sender = NULL
message_type = system
```

The serializer must expose system messages differently from normal user messages.

---

# 7. Product Inquiry Context

When a buyer starts a conversation from a product page:

```http
POST /v1/chat/conversations/
```

Request:

```json
{
    "seller_id": "seller-uuid",
    "product_id": "product-uuid"
}
```

The backend must:

1. Authenticate buyer
2. Validate seller
3. Validate product
4. Validate that product belongs to the seller
5. Get-or-create the conversation
6. Avoid duplicate conversations
7. Create a product inquiry message only when appropriate
8. Broadcast the product inquiry through WebSocket if the seller is connected

Product message should contain:

* product ID
* product name
* current price
* product image
* product URL if applicable

Do not trust frontend-supplied:

* product name
* price
* image
* seller identity

Always derive these from the database.

---

# 8. Product Inquiry Duplication Protection

Avoid creating the same inquiry repeatedly due to:

* double-click
* frontend retry
* network retry
* mobile reconnect
* API timeout followed by retry

Use appropriate idempotency logic.

If an idempotency mechanism already exists in the project, reuse it.

Otherwise implement a safe server-side strategy.

Do not solve duplicate prevention using only frontend flags.

---

# 9. WebSocket Architecture

Create:

```text
chat/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── consumers.py
├── middleware.py
├── routing.py
├── permissions.py
├── services.py
├── selectors.py
├── tests.py
└── migrations/
```

Prefer separating business logic from consumers.

The WebSocket consumer should NOT become a giant business-logic class.

Recommended architecture:

```text
Consumer
   ↓
Service Layer
   ↓
Selectors / ORM
   ↓
Database
```

---

# 10. WebSocket URL

Implement:

```text
ws/chat/<uuid:conversation_id>/
```

Example:

```text
ws/chat/550e8400-e29b-41d4-a716-446655440000/?token=<JWT>
```

---

# 11. JWT WebSocket Authentication

Implement custom middleware.

Authentication must support:

### Query parameter

```text
?token=<JWT>
```

### Authorization header

```text
Authorization: Bearer <JWT>
```

Prefer the Authorization header where the WebSocket client supports it.

Query-token support is required for browsers and environments where custom WebSocket headers are difficult.

---

# 12. JWT Security Requirements

Never:

* log JWT tokens
* store JWT tokens in database
* expose tokens in application logs
* return tokens in API responses
* accept malformed authentication
* silently accept expired tokens

The middleware must:

1. Extract token
2. Validate JWT signature
3. Validate expiration
4. Validate token type according to SimpleJWT configuration
5. Resolve user
6. Verify user is active
7. Attach user to:

```python
scope["user"]
```

Unauthenticated WebSocket connection must be rejected.

Use an appropriate WebSocket close code.

---

# 13. Conversation Authorization

This is a critical security boundary.

A user can connect to a conversation only if:

```text
user == conversation.buyer
OR
user == conversation.seller
```

Nobody else may:

* connect
* receive messages
* send messages
* read messages
* upload media
* download attachments
* retrieve conversation history

Do not rely on:

```text
conversation_id
```

as authorization.

Every sensitive operation must verify conversation membership server-side.

---

# 14. Horizontal Scaling

Do not use in-memory channel layers.

Configure:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                ("redis", 6379),
            ],
        },
    },
}
```

Use the existing Docker Redis service:

```text
townmarket_redis
redis:7-alpine
```

Do not create another Redis container unless the existing infrastructure requires it.

The architecture must work when multiple Django/ASGI workers are running.

Example:

```text
Client A
   ↓
ASGI Worker 1
   ↓
Redis
   ↓
ASGI Worker 2
   ↓
Client B
```

---

# 15. ASGI Configuration

Refactor `core/asgi.py` carefully.

Initialize Django early:

```python
django.setup()
```

or use the appropriate `get_asgi_application()` initialization pattern before importing application modules that depend on Django's app registry.

Then configure:

```text
ProtocolTypeRouter
├── HTTP
└── WebSocket
      ↓
JWTAuthMiddleware
      ↓
URLRouter
      ↓
ChatConsumer
```

Avoid `AppRegistryNotReady`.

Do not break existing HTTP APIs.

---

# 16. REST API

Implement:

### Conversation list

```http
GET /v1/chat/conversations/
```

Only return conversations belonging to the authenticated user.

Never return another user's conversations.

Sort by:

```text
last_message_at DESC
```

Recommended response:

```json
{
    "id": "uuid",
    "participant": {
        "id": "uuid",
        "name": "Seller",
        "phone": "...",
        "avatar": "..."
    },
    "last_message": {
        "id": "uuid",
        "type": "text",
        "content": "Hello",
        "created_at": "..."
    },
    "unread_count": 3,
    "last_message_at": "..."
}
```

---

# 17. Conversation Creation

```http
POST /v1/chat/conversations/
```

Request:

```json
{
    "seller_id": "uuid",
    "product_id": "uuid"
}
```

Rules:

* authenticated buyer only
* seller must exist
* seller must have correct role
* buyer cannot equal seller
* product must exist if supplied
* product must belong to seller
* conversation must be get-or-create
* database uniqueness must protect against race conditions

Use:

```python
transaction.atomic()
```

and database constraints.

Do not rely only on:

```python
if not Conversation.objects.filter(...).exists():
```

because concurrent requests can bypass this check.

---

# 18. Message History

```http
GET /v1/chat/conversations/<uuid:conversation_id>/messages/
```

Requirements:

* participant-only access
* pagination
* stable ordering
* newest/oldest strategy clearly documented
* proper database indexing

Prefer cursor pagination for large conversations if compatible with the existing API architecture.

Do not load the entire conversation into memory.

---

# 19. Text Messaging

WebSocket input:

```json
{
    "action": "send_message",
    "content": "Is this product available?"
}
```

Validate:

* authenticated user
* conversation membership
* message content
* maximum text length
* empty/whitespace-only content
* malicious input

Then:

```text
Validate
 ↓
transaction.atomic()
 ↓
create Message
 ↓
update Conversation.last_message_at
 ↓
broadcast
```

---

# 20. Transaction Consistency

Message creation and conversation metadata update must be handled safely.

Do not allow:

```text
Message created
BUT
Conversation.last_message_at not updated
```

or:

```text
Conversation timestamp updated
BUT
Message creation failed
```

Use an appropriate database transaction.

---

# 21. Message Broadcasting

Broadcast structured events rather than ORM objects.

Example:

```json
{
    "type": "message",
    "message": {
        "id": "uuid",
        "conversation_id": "uuid",
        "message_type": "text",
        "sender": {},
        "content": "Hello",
        "created_at": "...",
        "is_read": false
    }
}
```

Never broadcast:

* passwords
* JWT tokens
* private storage paths
* internal database metadata
* sensitive user information

---

# 22. Read Receipts

Client sends:

```json
{
    "action": "read_messages"
}
```

Server must:

1. Authenticate
2. Verify membership
3. Mark messages sent by the other participant as read
4. Set `read_at`
5. Avoid repeatedly updating already-read messages
6. Broadcast a compact read event

Example:

```json
{
    "type": "messages_read",
    "conversation_id": "uuid",
    "reader_id": "uuid",
    "read_at": "..."
}
```

Avoid updating every message unnecessarily.

Use an efficient queryset update.

---

# 23. Media Upload Architecture

Do NOT send binary files through WebSockets.

Use:

```http
POST /v1/chat/conversations/<uuid:conversation_id>/messages/media/
```

Multipart upload.

Required validation:

```text
file exists
file size < 10 MB
valid MIME type
conversation membership
authenticated user
```

10 MB:

```text
10,485,760 bytes
```

Files with:

```text
size >= 10,485,760
```

must be rejected.

The requirement is strict.

---

# 24. Media Security

Do not trust:

```text
Content-Type
filename
extension
```

from the browser.

Where practical, validate the actual file signature/content type.

Prevent:

* executable uploads
* dangerous HTML/SVG where applicable
* path traversal
* malicious filenames
* arbitrary filesystem paths
* unauthorized media access

Normalize filenames.

Never expose raw private filesystem paths.

---

# 25. Media Storage

Store attachments under:

```text
chat_attachments/
```

Use the existing Django storage backend.

Do not hard-code local filesystem assumptions if the project already supports:

* S3
* Cloudflare R2
* another object storage provider

The implementation must work with the existing storage architecture.

---

# 26. Secure Attachment Download

Endpoint:

```http
GET /v1/chat/messages/<uuid:message_id>/attachment/
```

Only:

* message sender
* conversation recipient

may access the attachment.

Authentication must support:

### Authorization header

```http
Authorization: Bearer <JWT>
```

### Short-lived query token

```text
?token=<JWT>
```

The query-token approach exists specifically so browser elements can load protected resources:

```html
<img>
<video>
<a>
```

Do not expose permanent public attachment URLs.

---

# 27. Attachment Authorization

The server must verify:

```text
authenticated user
        ↓
message
        ↓
conversation
        ↓
buyer OR seller
```

Never authorize solely because:

```text
message_id is valid
```

or because the user knows the attachment URL.

---

# 28. Attachment Response

Use secure streaming/file responses where appropriate.

Do not load a large file completely into application memory.

Set appropriate:

* Content-Type
* Content-Disposition
* caching headers
* security headers

Do not accidentally expose private storage URLs unless the architecture explicitly requires signed URLs.

---

# 29. Media WebSocket Event

After successful upload:

1. Save Message
2. Generate secure attachment representation
3. Broadcast:

```json
{
    "type": "message",
    "message": {
        "id": "uuid",
        "message_type": "media",
        "file_name": "image.jpg",
        "file_type": "image/jpeg",
        "file_size": 123456,
        "attachment_url": "/v1/chat/messages/<uuid>/attachment/"
    }
}
```

Do not broadcast raw binary data.

---

# 30. Serializer Design

Implement:

### UserSnippetSerializer

Fields:

```text
id
name
phone
avatar
```

Only expose fields that are appropriate for buyer-seller communication.

Do not leak:

* password
* internal permissions
* sensitive profile fields
* private metadata

---

### ConversationSerializer

Include:

```text
id
participant
last_message
unread_count
created_at
updated_at
last_message_at
```

Avoid N+1 queries.

Use:

* `select_related`
* `prefetch_related`
* annotations/subqueries where appropriate

Do not execute one query per conversation to calculate unread counts.

---

### MessageSerializer

Include:

```text
id
conversation
sender
message_type
content
product
attachment
file_name
file_type
file_size
created_at
is_read
read_at
```

Product information must be server-derived.

---

# 31. Query Optimization

Treat performance as a first-class requirement.

The following must be avoided:

```text
N+1 queries
```

Optimize conversation listing using:

* `select_related`
* `prefetch_related`
* `Count`
* conditional aggregation
* `Subquery`
* appropriate indexes

Conversation listing should remain efficient when a user has:

```text
100
1,000
10,000+
```

conversations.

Message history must be paginated.

Do not retrieve unnecessary columns.

---

# 32. Database Indexing

Add indexes based on actual query patterns.

At minimum evaluate:

```text
Conversation(buyer, seller)
Conversation(buyer, last_message_at)
Conversation(seller, last_message_at)
Message(conversation, created_at)
Message(conversation, is_read)
Message(sender, created_at)
```

Do not blindly add indexes without understanding write/read tradeoffs.

---

# 33. Concurrency and Race Conditions

Explicitly handle:

### Conversation creation race

Two requests simultaneously create the same buyer-seller conversation.

### Duplicate product inquiry

Frontend retry creates duplicate product messages.

### Read receipt race

Two devices mark messages as read simultaneously.

### Message ordering

Two messages arrive almost simultaneously.

### WebSocket reconnect

Client reconnects after network failure and retries a message.

### Media upload retry

Client retries after timeout although the server already saved the message.

Use:

* database constraints
* transactions
* atomic updates
* idempotency where appropriate

Do not depend on application-level `if exists` checks alone.

---

# 34. WebSocket Reconnection

The backend must tolerate clients reconnecting.

Frontend documentation must explain:

```text
connect
↓
authenticate
↓
load conversation history
↓
connect websocket
↓
receive real-time messages
↓
reconnect if disconnected
```

The backend must not create duplicate conversations/messages merely because the client reconnects.

---

# 35. Message Ordering

Do not assume WebSocket arrival order alone represents database order.

Use server-generated:

```text
created_at
```

and UUID/message IDs.

The frontend should sort based on server data.

Document the ordering semantics.

---

# 36. Security Requirements

Perform a dedicated security review.

Check:

* authentication bypass
* IDOR
* broken object-level authorization
* JWT validation
* expired tokens
* invalid tokens
* role escalation
* buyer impersonation
* seller impersonation
* unauthorized conversation access
* unauthorized message access
* unauthorized attachment access
* malicious uploads
* filename traversal
* MIME spoofing
* oversized files
* XSS through message content
* SQL injection
* CSRF implications for HTTP endpoints
* rate abuse
* WebSocket connection abuse
* information leakage
* excessive user data exposure

The most important security rule:

> Knowing a conversation UUID or message UUID must never be sufficient to access the resource.

---

# 37. Rate Limiting / Abuse Protection

Evaluate appropriate throttling for:

```text
conversation creation
message sending
media uploads
attachment downloads
WebSocket connections
```

If the project already has throttling infrastructure, integrate with it.

Do not introduce an incompatible rate-limiting system without justification.

---

# 38. HTML/XSS Protection

Messages are user-generated content.

Never render message content as trusted HTML.

Backend/frontend documentation must explicitly state that message content must be treated as plain text unless a secure sanitization pipeline is intentionally implemented.

---

# 39. Inactive/Banned User Handling

Inspect existing marketplace rules.

If:

* buyer is banned
* seller is banned
* seller account is inactive
* shop is inactive

determine whether communication must be blocked according to the existing business rules.

Do not invent conflicting marketplace behavior.

Document the final decision.

---

# 40. API Error Standards

Use the existing project's API error format.

Return appropriate errors for:

```text
401 Unauthorized
403 Forbidden
404 Not Found
400 Bad Request
413 Payload Too Large
```

For the explicit requirement, files:

```text
>= 10 MB
```

must be rejected as specified by the project API contract.

Do not expose internal exception traces.

---

# 41. REST/WebSocket Separation

REST should handle:

```text
conversation creation
conversation listing
message history
media upload
attachment download
```

WebSocket should handle:

```text
real-time messages
read receipts
real-time media notification
real-time conversation updates
```

Do not duplicate business logic between REST views and WebSocket consumers.

Both should call shared service-layer functions.

---

# 42. Recommended Service Layer

Create services such as:

```text
ConversationService
MessageService
MediaMessageService
ReadReceiptService
```

or equivalent project-compatible architecture.

Example conceptual API:

```python
ConversationService.get_or_create_conversation(...)
MessageService.create_text_message(...)
MessageService.create_media_message(...)
MessageService.mark_as_read(...)
```

The exact implementation should follow existing project conventions.

---

# 43. Selectors

Use selectors for complex reads where appropriate:

```python
get_user_conversations(...)
get_conversation_messages(...)
get_conversation_for_user(...)
get_unread_count(...)
```

This keeps views and consumers thin.

---

# 44. Admin

Register:

```text
Conversation
Message
```

in Django Admin.

Admin should provide useful filtering/searching for:

* buyer
* seller
* message type
* created date
* read status

Be careful about exposing sensitive attachment information unnecessarily.

---

# 45. Logging

Add useful structured logs for:

* authentication failure
* unauthorized conversation access
* media upload rejection
* attachment access denial
* WebSocket connection errors
* unexpected server failures

Never log:

```text
JWT
password
full private message content
private attachment URL/token
```

---

# 46. Tests

Create comprehensive tests.

Minimum coverage:

## Model tests

* conversation UUID
* unique buyer/seller
* buyer != seller
* message relationships
* message types
* timestamps

## API tests

* create conversation
* retrieve existing conversation
* invalid seller
* invalid product
* product belongs to another seller
* unauthorized conversation
* conversation list isolation
* message pagination
* unread count
* read status

## Product inquiry tests

* product context created
* correct product information
* correct seller
* duplicate request handling
* invalid product
* product belonging to another seller

## Media tests

* valid file
* file below 10 MB
* file exactly 10 MB
* file above 10 MB
* invalid MIME type
* unauthorized upload
* unauthorized download
* sender download
* recipient download
* unknown message ID

## Security tests

Explicitly prove:

```text
User A cannot access User B's conversation
User A cannot read User B's messages
User A cannot upload to User B's conversation
User A cannot download User B's attachment
User A cannot connect to User B's WebSocket
```

Do not merely test successful cases.

---

# 47. WebSocket Tests

Use:

```python
WebsocketCommunicator
```

Test:

* valid JWT
* invalid JWT
* expired JWT
* missing token
* participant connection
* non-participant rejection
* text message sending
* message broadcast
* read receipts
* unauthorized actions
* reconnect behavior where practical

---

# 48. Performance Tests

Evaluate:

* conversation list query count
* message list query count
* serializer query count
* unread count query count
* concurrent conversation creation
* concurrent message creation

Use Django query assertions where practical.

The implementation must not introduce obvious N+1 behavior.

---

# 49. Docker Integration

Update:

```text
requirements.txt
requirements-docker.txt
```

with:

```text
channels-redis==4.2.1
```

Verify Docker dependency installation.

Use existing Redis:

```text
redis:7-alpine
```

with hostname:

```text
redis
```

and port:

```text
6379
```

Verify:

```text
Django → Channels → Redis → WebSocket
```

works inside Docker networking.

---

# 50. Files To Modify/Create

### Modify

```text
requirements.txt
requirements-docker.txt
core/settings.py
core/config.py
core/asgi.py
core/urls.py
docker-compose.base.yml
```

Only modify Docker configuration if necessary.

### Create

```text
chat/__init__.py
chat/apps.py
chat/models.py
chat/serializers.py
chat/views.py
chat/urls.py
chat/consumers.py
chat/routing.py
chat/middleware.py
chat/permissions.py
chat/services.py
chat/selectors.py
chat/admin.py
chat/tests.py
chat/migrations/...
docs/chat_integration_guide.md
```

Adjust this structure if the existing project has established architectural conventions.

---

# 51. Frontend Integration Guide

Create:

```text
docs/chat_integration_guide.md
```

It must document:

## Authentication

How to obtain/use JWT.

## WebSocket

Example:

```text
ws://host/ws/chat/<conversation_id>/?token=<JWT>
```

and HTTPS production:

```text
wss://host/ws/chat/<conversation_id>/?token=<JWT>
```

## Events

Document:

```text
send_message
message
read_messages
messages_read
```

## REST APIs

Document all endpoints.

## Media Upload

Document multipart upload.

## Attachment Rendering

Show how frontend can use:

```text
<img>
<video>
<a>
```

with short-lived authenticated URLs.

## Reconnection

Provide recommended reconnect strategy.

## Pagination

Explain message history pagination.

## Unread Count

Explain conversation-level unread counts.

## Product Inquiry

Explain how:

```json
{
    "seller_id": "...",
    "product_id": "..."
}
```

creates a product-context conversation message.

---

# 52. Production Configuration

Verify:

```text
ASGI server
Redis
Channels
Django
Database
Storage
JWT
CORS
CSRF
Allowed Hosts
WebSocket origin/security configuration
```

Do not assume the Django development server is sufficient for production.

Document the expected production topology.

Example:

```text
Nginx / Load Balancer
        ↓
ASGI Workers
        ↓
Django Channels
        ↓
Redis
        ↓
PostgreSQL
        ↓
Object Storage
```

---

# 53. Migration Safety

Generate Django migrations.

Verify migrations work from:

```text
empty database
```

and:

```text
existing production-like database
```

Do not make destructive schema changes.

---

# 54. Backward Compatibility

Existing REST APIs must continue working.

Verify:

* existing authentication
* product APIs
* seller APIs
* buyer APIs
* media handling
* Docker startup
* Celery
* Redis
* ASGI
* WSGI if still used

No unrelated API behavior should change.

---

# 55. Definition of Done

The implementation is complete only when all of the following are true:

* [ ] Django Channels configured
* [ ] Redis channel layer configured
* [ ] `channels-redis==4.2.1` added
* [ ] Chat app registered
* [ ] ASGI routing works
* [ ] JWT WebSocket authentication works
* [ ] Conversation authorization works
* [ ] Buyer/seller role validation works
* [ ] Conversation uniqueness enforced at DB level
* [ ] Product inquiry context works
* [ ] Duplicate inquiry protection implemented
* [ ] Text messaging works
* [ ] Read receipts work
* [ ] Media upload works
* [ ] 10 MB strict limit enforced
* [ ] Secure attachment download works
* [ ] Authorization header works
* [ ] Query token works
* [ ] Unauthorized attachment access rejected
* [ ] Conversation listing works
* [ ] Pagination works
* [ ] Unread counts work
* [ ] N+1 queries eliminated
* [ ] Appropriate indexes added
* [ ] Transaction boundaries implemented
* [ ] Race conditions considered
* [ ] WebSocket broadcasts work across workers
* [ ] Security tests pass
* [ ] API tests pass
* [ ] WebSocket tests pass
* [ ] Docker integration works
* [ ] Existing APIs remain functional
* [ ] Admin configured
* [ ] Documentation completed

---

# 56. Final Engineering Audit

After implementation, do NOT stop at "tests pass".

Perform a final audit as a **Staff Backend Engineer**.

Review the complete implementation for:

### Architecture

* Is business logic duplicated?
* Are consumers too large?
* Are services/selectors appropriately separated?
* Is the implementation compatible with the existing architecture?

### Security

* Can another user access a conversation by guessing UUID?
* Can another user access an attachment?
* Can another user connect to the WebSocket?
* Can a buyer impersonate a seller?
* Can a seller impersonate a buyer?
* Can expired JWTs connect?
* Can malicious files be uploaded?

### Database

* Are constraints correct?
* Are indexes appropriate?
* Are race conditions handled?
* Are transactions correct?

### Performance

* Any N+1?
* Any unnecessary queries?
* Any unbounded queryset?
* Any large file loaded into memory?
* Any inefficient unread-count calculation?

### Reliability

* What happens if Redis temporarily fails?
* What happens if WebSocket reconnects?
* What happens if API request retries?
* What happens if two messages are sent simultaneously?
* What happens if media upload succeeds but WebSocket delivery fails?

### Scalability

Evaluate the architecture assuming:

```text
100,000+ users
10,000+ concurrent WebSocket connections
millions of messages
large media volume
multiple ASGI workers
multiple application servers
```

Identify bottlenecks and document any architectural limitations.

---

# 57. Required Final Output

After implementation, provide:

## 1. Implementation Summary

Explain exactly what was implemented.

## 2. Changed Files

List every modified and newly created file.

## 3. Database Changes

Explain models, constraints, indexes, and migrations.

## 4. API Documentation

List every endpoint with request/response examples.

## 5. WebSocket Protocol

Document connection format and every event.

## 6. Security Audit

List security controls implemented and any remaining risks.

## 7. Performance Audit

Report query optimization and N+1 analysis.

## 8. Test Results

Report:

```text
Total tests
Passed
Failed
Skipped
```

Do not claim tests passed unless they were actually executed.

## 9. Docker Verification

Verify Redis + Channels + ASGI integration.

## 10. Known Limitations

Clearly identify anything intentionally not implemented.

---

# Critical Engineering Rule

Do not take shortcuts.

Do not implement authorization only in serializers.

Do not trust frontend-supplied buyer/seller/product information.

Do not use in-memory WebSocket channel layers.

Do not send files through WebSockets.

Do not expose public attachment URLs.

Do not use only application-level uniqueness checks.

Do not introduce N+1 queries.

Do not put all business logic inside the WebSocket consumer.

Do not claim production readiness without running the relevant tests.

The final implementation must behave like a **real marketplace messaging subsystem**, not a demo chat application.
