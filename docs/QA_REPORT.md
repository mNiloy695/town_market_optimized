You are a **Senior QA Engineer / QA Architect / Security QA Engineer**. Perform a **deep, production-grade QA audit** of this entire project.

Do not limit the review to obvious bugs or happy-path testing. Assume this system will handle **real users, concurrent requests, financial/business-critical operations, retries, malicious users, network failures, duplicate requests, partial failures, and high traffic**.

Your objective is to identify **functional bugs, corner cases, transaction/data-integrity problems, idempotency failures, concurrency/race conditions, security vulnerabilities, API problems, performance issues, and architectural weaknesses**.

---

# 1. Understand the System First

Before testing:

* Understand the complete architecture.
* Identify backend/frontend/services/database/cache/queue/external integrations.
* Identify all important business entities and their relationships.
* Identify state machines and status transitions.
* Identify financial/payment/earning/referral/withdrawal/order/booking-related flows.
* Identify asynchronous operations and Celery/background jobs.
* Identify external API/webhook integrations.
* Identify authentication and authorization boundaries.
* Identify critical database transactions.

Create a concise **System Understanding Map** before reporting bugs.

---

# 2. Functional QA

Test every major feature from:

### Happy Path

* Valid input
* Valid state transitions
* Normal user flow
* Expected successful response

### Negative Path

* Missing fields
* Null values
* Empty strings
* Wrong data types
* Invalid UUIDs
* Invalid IDs
* Invalid status values
* Invalid dates
* Invalid amounts
* Negative numbers
* Zero values
* Extremely large values
* Duplicate values
* Invalid relationships
* Deleted/nonexistent objects

### Boundary Testing

Test:

* 0
* 1
* -1
* Maximum allowed value
* Maximum + 1
* Minimum allowed value
* Minimum - 1
* Empty collections
* One-item collections
* Very large collections
* Very long strings
* Unicode
* Special characters
* Whitespace
* Duplicate records

---

# 3. State Transition Testing

For every important model/status field, identify the state machine.

For example:

```text
PENDING
  ↓
PROCESSING
  ↓
COMPLETED
```

Test:

* Valid transitions
* Invalid transitions
* Repeated transitions
* Backward transitions
* Transition after deletion
* Transition after cancellation
* Transition after completion
* Concurrent transitions
* Transition after timeout
* Transition after retry

Find cases where the API allows an **impossible business state**.

Example:

```text
COMPLETED → PENDING
PAID → UNPAID
CANCELLED → COMPLETED
WITHDRAWN → AVAILABLE
```

---

# 4. Transaction & Database Integrity

This is a critical part of the audit.

Inspect every operation that modifies multiple records.

Look for:

* Missing `transaction.atomic()`
* Partial database updates
* Multiple writes where one can fail
* Database state becoming inconsistent
* Incorrect transaction boundaries
* Nested transactions
* Incorrect rollback behavior
* Exceptions occurring after partial writes
* External API call inside database transaction
* Database commit before external operation succeeds
* External operation succeeding while DB transaction fails
* DB operation succeeding while external operation fails

For every critical workflow answer:

> What happens if the process crashes exactly here?

Test crash points such as:

```text
Before DB write
After DB write
After first DB write
Before second DB write
After DB commit
Before external API call
After external API succeeds
After external API fails
Before Celery task
After Celery task starts
During Celery retry
```

Identify all possible **partial-success states**.

---

# 5. Idempotency Testing

Aggressively test duplicate requests.

For every mutation endpoint ask:

> What happens if the exact same request is sent 2, 5, 10, or 100 times?

Test:

* Duplicate POST
* Duplicate PATCH
* Duplicate PUT
* Duplicate DELETE
* Duplicate webhook
* Duplicate payment callback
* Duplicate Celery task
* Client retry after timeout
* Browser double-click
* Mobile retry
* Reverse proxy retry
* Worker retry

Especially inspect:

* Payment creation
* Payment confirmation
* Order creation
* Referral earnings
* Commission calculation
* Wallet operations
* Withdrawals
* Refunds
* Booking creation
* Booking cancellation
* External API synchronization

Determine whether the system has proper:

* Idempotency keys
* Unique constraints
* Database constraints
* Event IDs
* Webhook IDs
* Deduplication
* Atomic updates

Do not assume Celery retry means idempotency.

---

# 6. Race Conditions & Concurrency

Assume multiple requests happen simultaneously.

Test:

```text
User A + User A
User A + User B
Admin + User
Two Celery workers
Two webhook deliveries
Two payment callbacks
Two withdrawal requests
Two order confirmations
```

Look for:

* Lost updates
* Double spending
* Double earnings
* Duplicate commissions
* Duplicate records
* Incorrect counters
* Stale reads
* TOCTOU vulnerabilities
* Missing row locks
* Missing `select_for_update()`
* Incorrect isolation assumptions
* Race conditions between validation and update

Pay special attention to:

```python
if balance >= amount:
    balance -= amount
```

and similar read-modify-write operations.

Determine whether concurrent requests can both pass validation.

---

# 7. Financial / Money Logic

If the system handles money, perform a dedicated financial audit.

Check:

* Decimal vs float
* Currency precision
* Rounding
* Decimal places
* Negative amounts
* Zero amounts
* Huge amounts
* Currency conversion
* Fees
* Taxes
* Commission calculation
* Refund calculation
* Partial refunds
* Duplicate payment
* Payment mismatch
* Overpayment
* Underpayment
* Balance calculation
* Available balance
* Pending balance
* Withdrawable balance

Verify accounting invariants.

Example:

```text
Total balance = available + pending + locked
```

Find any situation where money can:

* Appear from nowhere
* Disappear
* Be counted twice
* Be withdrawn twice
* Be refunded twice
* Be earned twice

---

# 8. Webhook Security & Reliability

Audit every webhook.

Test:

* Duplicate webhook
* Out-of-order webhook
* Delayed webhook
* Invalid signature
* Missing signature
* Invalid amount
* Invalid order ID
* Invalid timestamp
* Replay attack
* Wrong payment status
* Wrong currency
* Already-completed transaction
* Unknown transaction
* Webhook arriving after cancellation
* Webhook arriving after refund

Verify:

* Signature verification
* Replay protection
* Idempotency
* Atomic updates
* Event ordering
* Response behavior
* Retry compatibility

---

# 9. Authentication & Authorization

Perform an IDOR/BOLA audit.

Try changing:

```text
/user/123
/user/124
/order/123
/order/124
/company/123
/company/124
/wallet/123
/wallet/124
```

Test whether a user can access another user's:

* Profile
* Orders
* Payments
* Wallet
* Earnings
* Referrals
* Withdrawals
* Private files
* Admin data

Check:

* Role permissions
* Object-level permissions
* Admin endpoints
* Staff endpoints
* Superuser behavior
* Ownership validation
* Horizontal privilege escalation
* Vertical privilege escalation

---

# 10. Security Audit

Perform a high-level OWASP-style security review.

Look for:

* IDOR/BOLA
* Broken access control
* SQL injection
* Command injection
* XSS
* CSRF
* SSRF
* File upload vulnerabilities
* Path traversal
* Mass assignment
* Sensitive data exposure
* Excessive data returned by APIs
* Weak validation
* Authentication bypass
* Authorization bypass
* JWT problems
* Token leakage
* Secret leakage
* Debug mode
* Stack traces
* Internal error exposure
* Unsafe CORS
* Weak rate limiting
* Brute-force possibilities
* Enumeration attacks
* Insecure password reset
* Insecure email verification
* Session issues

Check `.env`, configuration, logs, Docker configuration, CI/CD configuration and repository history for secrets.

Never expose discovered secrets in the report; identify them safely.

---

# 11. API QA

For every API inspect:

* HTTP method correctness
* Status codes
* Request validation
* Response schema
* Pagination
* Filtering
* Searching
* Sorting
* Ordering
* Authentication
* Authorization
* Error handling
* Rate limiting
* Consistent response format
* Sensitive fields
* N+1 queries
* Excessive query parameters
* Unexpected parameter combinations

Test:

```text
?page=0
?page=-1
?page=999999999
?page_size=0
?page_size=1000000
```

and malicious/invalid filter combinations.

Check whether users can manipulate filters to access unauthorized records.

---

# 12. Search & Filtering

Test combinations such as:

```text
search + filter
search + pagination
search + ordering
multiple filters
invalid filters
empty filters
very long search
special characters
Unicode
SQL-like strings
case sensitivity
```

Check performance and correctness.

---

# 13. Pagination

Test:

* Empty page
* Last page
* Page beyond last page
* Large page size
* Negative page
* Deleted records between requests
* New records inserted between requests
* Duplicate/missing records across pages

Check whether pagination leaks unauthorized data.

---

# 14. Background Jobs / Celery

Audit every background task.

For each task test:

* Retry
* Duplicate execution
* Worker crash
* Timeout
* Network failure
* External API failure
* DB failure
* Partial completion
* Task ordering
* Task expiration
* Multiple workers

Ask:

> Can this task safely execute twice?

If not, identify the missing idempotency mechanism.

Check retry configuration for:

* Infinite retries
* Incorrect backoff
* Retry storms
* Duplicate side effects
* Non-retryable errors being retried
* Retryable errors not being retried

---

# 15. External API Integrations

For every third-party integration test:

```text
200
201
400
401
403
404
409
429
500
502
503
504
timeout
connection reset
malformed response
slow response
duplicate response
```

Determine whether the system remains consistent when the external service is unavailable.

Check timeout configuration.

Never allow an external API call to cause indefinite blocking.

---

# 16. Cache / Redis

Check:

* Cache invalidation
* Stale data
* Incorrect cache keys
* User data leaking between users
* Cache poisoning
* Race conditions
* TTL problems
* Missing invalidation after mutation
* Redis failure behavior

Test behavior when Redis is unavailable.

---

# 17. Data Integrity & Constraints

Inspect database models and migrations.

Look for missing:

* Unique constraints
* Foreign keys
* Check constraints
* Not-null constraints
* Proper indexes
* Composite indexes
* Unique combinations

Ask:

> Is business-critical integrity enforced only in Python, or also at the database level?

Anything critical should not rely exclusively on application-level validation.

---

# 18. Deletion & Lifecycle Testing

Test:

* Delete parent
* Delete child
* Soft delete
* Hard delete
* Restore
* Archived records
* Deleted user
* Deleted company
* Deleted order
* Deleted payment
* Deleted referral

Check:

* `CASCADE`
* `PROTECT`
* `SET_NULL`

Make sure historical financial/audit records cannot accidentally disappear.

---

# 19. Time / Date / Timezone

Test:

* UTC
* Local timezone
* DST
* Midnight
* Month-end
* Year-end
* Leap year
* Daylight saving transitions
* Expiration boundaries
* `start == end`
* `start > end`
* Exactly-at-expiration
* One second before/after expiration

Look for naive vs aware datetime issues.

---

# 20. Performance QA

Identify:

* N+1 queries
* Missing indexes
* Expensive joins
* `icontains` on large tables
* Large queryset evaluation
* Unbounded queries
* Excessive serialization
* Large API responses
* Slow aggregation
* Repeated database queries

Estimate behavior at:

```text
1K users
10K users
100K users
1M users
10M records
```

Identify endpoints likely to degrade.

---

# 21. Observability

Check:

* Logging
* Error logging
* Request IDs
* Correlation IDs
* Audit logs
* Financial event logs
* Security events
* Celery task logs
* Webhook logs

Ensure logs do NOT contain:

* Passwords
* JWTs
* API keys
* Payment credentials
* Sensitive personal data

---

# 22. Error Handling

Force failures everywhere.

Check whether errors:

* Roll back correctly
* Return correct HTTP status
* Return safe messages
* Preserve useful debugging information in logs
* Leak internal implementation details
* Expose database errors
* Expose stack traces
* Leave partial data

Test generic exceptions and unexpected failures.

---

# 23. Business Invariants

Identify the most important business rules and convert them into invariants.

Examples:

```text
A completed payment cannot become unpaid.
A wallet cannot have a negative available balance.
A commission cannot be created twice for the same source event.
A withdrawal cannot be processed twice.
A cancelled order cannot generate new earnings.
A deleted user cannot access protected resources.
A webhook event must be processed at most once.
```

For every invariant:

1. Define it.
2. Identify where it is enforced.
3. Try to violate it.
4. Report if it can be violated.

---

# 24. Test Matrix

Create a test matrix containing:

| Area | Scenario | Expected | Actual | Severity | Risk |
| ---- | -------- | -------- | ------ | -------- | ---- |

Prioritize:

### P0 — Critical

* Money loss
* Duplicate payment
* Authentication bypass
* Authorization bypass
* Data corruption
* Double withdrawal
* Critical security vulnerability

### P1 — High

* Major business logic failure
* Transaction inconsistency
* Race condition
* Significant data exposure
* Critical workflow broken

### P2 — Medium

* Incorrect behavior with workaround
* Performance issue
* Validation issue

### P3 — Low

* Minor UX/API inconsistency
* Cosmetic/non-critical issue

---

# 25. For Every Finding

Use this exact structure:

```text
ID:
Title:
Severity:
Priority:
Category:

Affected Component:
Affected Endpoint:
Affected Model:

Precondition:

Steps to Reproduce:

Expected Result:

Actual Result:

Technical Root Cause:

Business Impact:

Security Impact:

Data Integrity Impact:

Concurrency Impact:

Recommended Fix:

Regression Test:

Confidence:
```

Do not report vague issues.

Every bug must have a reproducible scenario.

---

# 26. Special Focus: Hidden Bugs

Actively search for bugs that normal QA usually misses:

* Double-click submission
* Request retry after timeout
* Browser refresh during mutation
* Mobile network switching
* Duplicate webhook
* Out-of-order webhook
* Celery retry after successful DB write
* Two workers processing the same object
* Admin action concurrent with user action
* Record deleted during transaction
* Permission revoked while request is running
* Payment succeeds but response is lost
* External API succeeds but DB update fails
* DB succeeds but external API fails
* Cache contains stale authorization data
* Expiration occurs during processing
* Month/year boundary
* Duplicate referral event
* Duplicate commission
* Duplicate withdrawal
* Negative/zero monetary values
* Integer overflow/very large values
* Floating-point rounding
* Unicode normalization
* Case sensitivity
* Empty vs NULL
* Soft-deleted objects being returned
* Historical records being modified

---

# 27. Final Deliverables

At the end provide:

## A. Executive Summary

* Overall QA risk level
* Production readiness
* Most dangerous problems
* Biggest data-integrity risks
* Biggest security risks

## B. Critical Findings

Rank the top 10 most dangerous issues.

## C. Complete Bug List

Group by:

* Functional
* Transaction
* Idempotency
* Concurrency
* Security
* Financial
* API
* Database
* Celery
* External integrations
* Performance
* Data integrity
* Edge cases

## D. Risk Heatmap

Rate each area:

```text
Critical
High
Medium
Low
```

## E. Production Readiness

Give one of:

```text
NOT READY
READY WITH CRITICAL FIXES
READY WITH MINOR FIXES
PRODUCTION READY
```

Explain exactly why.

## F. Recommended Fix Priority

Create:

```text
Fix Immediately
Fix Before Production
Fix Soon
Technical Debt
Optional Improvement
```

## G. Regression Test Plan

For every P0/P1 issue, propose a regression test.

---

# Important QA Rules

1. Do not assume the code is correct.
2. Do not only test happy paths.
3. Think like a malicious user.
4. Think like a concurrent user.
5. Think like a network failure.
6. Think like a database failure.
7. Think like a Celery retry.
8. Think like a duplicate webhook.
9. Think like a payment provider retry.
10. Think like a user clicking the same button 10 times.
11. Think about what happens if the process crashes at every important step.
12. Think about data integrity before API response correctness.
13. Prioritize real business impact over cosmetic issues.
14. Do not invent bugs without evidence.
15. Clearly distinguish confirmed bugs from potential risks.
16. Trace every important issue back to the exact code/model/query/endpoint responsible.
17. If something cannot be verified statically, mark it as **Needs Runtime Verification**.
18. Look for interactions between multiple components, not just isolated functions.
19. Assume production traffic is concurrent.
20. Treat financial operations and authorization as highest-risk areas.

Perform the audit as if you are signing off the system for a **real production deployment**.

---

# 28. Deployment & Runtime Commands

## 28.1 Development Mode
Start both backend and frontend locally with SQLite:
```bash
bash run.sh dev
```
- Django: http://127.0.0.1:8000 (SQLite)
- React: http://127.0.0.1:3000
- Database: SQLite (no PostgreSQL required)

## 28.2 Production Mode
Start both backend and frontend with PostgreSQL:
```bash
bash run.sh prod
```
- Django: http://127.0.0.1:8000 (PostgreSQL)
- React: http://127.0.0.1:3000
- Database: PostgreSQL (ensure running)

## 28.3 PostgreSQL Connectivity
Production database connection string:
```
DATABASE_URL=postgresql://townmarket:password@db:5432/townmarket
```
- Host: `db` (Docker Compose service name) or `localhost`/`127.0.0.1` (local)
- Port: `5432` (default PostgreSQL) or `5431` (Docker mapped port)
- User: `townmarket`
- Password: `password`
- Database: `townmarket`

## 28.4 Docker Database Access
```bash
# Connect to PostgreSQL inside Docker
docker exec -it town_market_db_1 psql -U townmarket -d townmarket

# Check Docker database status
docker-compose exec web python manage.py dbshell

# Run migrations
docker-compose exec web python manage.py migrate
```

## 28.5 Local PostgreSQL (Outside Docker)
If running outside Docker, update .env to use localhost:
```
DATABASE_URL=postgresql://townmarket:password@localhost:5432/townmarket
POSTGRES_HOST_PORT=5432
```
Then ensure PostgreSQL is running locally:
```bash
# Start PostgreSQL locally
pg_lsclusters
pg_ctlcluster <version> main start

# Or using Docker Compose
docker-compose up -d db
```

## 28.6 Database Commands
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Check database status
python manage.py check

# Access database shell
python manage.py dbshell
```
