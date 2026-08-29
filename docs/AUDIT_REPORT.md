# Town Market — Security & Production-Readiness Audit

Audit date: 2026-08-29 · Scope: full backend audit + P0/P1 remediation.

---

## 1. Executive summary

Read-only audit followed by remediation of the highest-priority findings.
All fixes below are implemented, verified with `manage.py check`, migration
generation, and the accounts/order test suites (all green in this environment).

- **P0 secrets exposure**: resolved (untracked + purge from history pending
  one force-push, see §7).
- **P0 broken production storage**: resolved (working R2/S3 backend with a
  safe local fallback).
- **P1 payment/money handling, refunds, OTP, prod ASGI**: resolved.
- **P2** (perf/polish): catalogued in §6, deferred by owner decision.

---

## 2. Critical findings

| # | Severity | Finding | Location | Status |
|---|----------|---------|----------|--------|
| C1 | P0 | `.env.dev` committed to git with live-looking secrets (`STORE_ID`, `STORE_PASSWORD`, `SMS_API_KEY`, `NGROK_AUTHTOKEN`, DB creds) | repo history, commit `e738bbd` | untracked; history purge pending (force-push) |
| C2 | P0 | `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE` pointed at `storages.backends.cloudflare.CloudFileStorage`, which does not exist in installed `django-storages==1.14.6` → every upload and prod `collectstatic` crashes | `core/settings.py` (old) | fixed (§3.2) |
| C3 | P0 | Real R2 credentials unusable: no S3 endpoint mapping, boto3 not installed | `requirements-docker.txt` | fixed (§3.2) |
| C4 | P0 | Prod compose runs `gunicorn core.wsgi` → no WebSocket/chat support; also `collectstatic` would abort boot, and runserver CMD in Dockerfile | `docker-compose.prod.yml`, `Dockerfile` | fixed (§3.6) |

## 3. Remediation applied (P0 + P1)

### 3.1 Secrets hygiene
- `.gitignore` now ignores `.env`, `.env.*`, keeps `!.env.example`.
- `git rm --cached .env.dev` (file untracked; `.env.example` remains as template).
- `.env.example` rewritten as a complete, safe template (no real values).
- Live keys in `.env`/`.env.dev` (and anything ever printed to logs) must be
  **rotated** at the providers (SSLCommerz store password, bKash, SMS API key,
  R2 tokens, NGROK auth) — see §7.

### 3.2 Cloudflare R2 storage (working S3-compatible backend)
- `core/settings.py` now defines a single `STORAGES` block:
  - If real R2 credentials are present (`CLOUDFLARE_R2_ACCOUNT_ID`, `_ACCESS_KEY_ID`,
    `_SECRET_ACCESS_KEY`, `_BUCKET_NAME`) → `storages.backends.s3boto3.S3Boto3Storage`
    (media) and `S3StaticStorage` (static), endpoint
    `https://<account_id>.r2.cloudflarestorage.com`, region `auto`, virtual addressing,
    `public-read` ACL, cache-control headers, no file overwrite.
  - Placeholder values (`your_r2_*`) are treated as unconfigured.
  - Otherwise → local `FileSystemStorage`/`StaticFilesStorage` (dev).
- `requirements-docker.txt`: added `boto3>=1.34.0` (required by the S3 backend) and
  `channels` + `daphne` (see §3.6).

### 3.3 Payment-gateway URLs fail-fast
- New `_gateway_url()` helper in settings refuses the sandbox defaults
  (`SSLCOMMERZ_API_URL`, `SSLCOMMERZ_VALIDATION_URL`, `BKASH_BASE_URL` →
  `sandbox.*`) whenever `DEBUG=False` and the env var isn't explicitly set
  (`ImproperlyConfigured` at boot, not a runtime leak).

### 3.4 Refunds (manual-reconciliation model — owner decision)
- New `order.models.RefundRecord` (+ migration `order/0010_refundrecord.py`)
  records a refund owed to a customer that an operator completes manually at the
  gateway. It stores `order`, optional `shop_order`, `gateway`, gateway
  transaction id, `amount`, `reason`, status (`pending|processed|declined`),
  creators/resolvers.
- Refund records are now written (never auto-submitted to the gateway) by:
  - Customer cancellation of a **confirmed** (paid) order in the 20-minute
    window → `Order.cancel_order` (`order/models/order.py`).
  - Vendor cancellation of a paid shop order (confirmed/processing) →
    `VendorOrderStatusUpdateView` (`order/views/vendor.py`), which now also
    **restores stock** and correctly **releases `reserved_quantity`** for
    `pending` cancels (previously neither happened).
  - Return approval → `VendorReturnApprovalView` now records a refund record and
    timeline text says "refund pending manual processing" (previously claimed
    "refund processed" with no refund).
- Admin: new `RefundRecordAdmin` queue (`/admin/order/refundrecord/`) with
  search by order/transaction id, list filters, and `mark processed/declined`
  actions (resolves against the identity that acted).

### 3.5 Money-deducted tracking
- bKash success callback (`order/views/bkash.py`): on **amount mismatch** or a
  **confirmation error** (bKash charged but the order was not confirmed), it now
  records/updates `MoneyDectedButOrderFailed` and marks the invoice
  `MONEY_DEDUCTED_ORDER_FAILED` — parity with the SSLCommerz webhook path, so
  manual reconciliation has a complete ledger.

### 3.6 Production ASGI (chat) + deploy hygiene
- `docker-compose.prod.yml`: `gunicorn` → `daphne -b 0.0.0.0 -p 8000 core.asgi:application`
  (WebSocket chat now served in prod). `requirements-docker.txt` gained
  `daphne==4.2.1` and `channels==4.3.2`.
- `Dockerfile` still uses `runserver` as CMD — overridden by the compose
  command in prod, but should be removed from `run.sh`/dev flows (recommendation §5).

### 3.7 OTP / password hardening (`accounts`)
- 6-digit, cryptographically-random codes (`secrets.randbelow`, zero-padded) via
  `OTP.generate_code()`; constant-time compare (`secrets.compare_digest`) in
  every verification path.
- **Resend can no longer bypass lockout**: OTP rows track `resend_attempts` /
  `resend_locked_until`; repeated resends lock the phone, and a phone-level
  lock blocks new OTP issuance (migration `accounts/0010_...`).
- **Enumeration closed**: `ForgotPasswordandResendView`, `VerifyOTPView`,
  `ResetPasswordView`, `ActiveUserAccountView` return uniform responses for
  unknown phone / bad code / cooldown (single generic message for forgot/resend).
- **Password policy enforced** on reset and on authenticated change
  (`validate_password`), previously missing.
- **Scoped throttling** for all public OTP endpoints (`otp: 5/minute` via
  `ScopedRateThrottle` in addition to global anon/user throttles).
- Dead duplicate OTP views removed from `accounts/views/auth.py` (now re-export
  from `accounts/views/otp.py`) to stop logic drift.
- Tests updated: reset no longer asserts auto-activation; added tests that reset
  preserves activation state and rejects weak passwords. `accounts` (18) and
  `order` (4) suites pass.

---

## 4. Deployment checklist (before Go-Live)

1. Rotate every secret that was exposed (see §2/C1).
2. Create `.env` from `.env.example`: real `SECRET_KEY` (strong, random), strong DB
   password, real R2 credentials, live SSLCommerz/bKash credentials + live URLs.
3. Run `python manage.py migrate` (new migrations:
   `accounts/0010_otp_...`, `order/0010_refundrecord`).
4. `docker-compose.prod.yml` boots Daphne → confirm WebSocket upgrade works
   through nginx (`Upgrade`/`Connection: upgrade` headers; TLS via host proxy —
   current nginx is HTTP-only, see §5).
5. Add `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` matching the real domain.
6. Verify `collectstatic` uploads to R2 bucket (bucket public-read) and media
   URLs resolve via R2 custom domain if configured.

---

## 5. Recommendations (not fixed)

- **nginx**: HTTP-only, host port 8082. Terminate TLS or proxy behind HTTPS and
  enable HSTS; add `Upgrade`/`Connection: upgrade` for WebSockets.
- **CSP**: `default-src 'self' http: https: data:` is weak; tighten to explicit
  origins (no scheme wildcards).
- **`Dockerfile` CMD** is `runserver`; change to a WSGI/ASGI worker or remove so
  production can never accidentally boot dev server.
- **`core/config.py`** is a dead parallel config module (nothing imports it);
  delete it to avoid confusion and duplicate secret paths.
- **Invoice amount** excludes shipping (signal fires before final total). Align
  invoice amount with the final paid amount.
- **Checkout** catches `except Exception → 500`; gateway call happens inside
  `transaction.atomic()`; returns 201 even when payment fails. Restructure to
  collect payment-hosted URL outside the transaction and return the correct code.
- **`core/urls.py`** serves media only when `DEBUG`; R2 media URLs must come from
  `AWS_S3_CUSTOM_DOMAIN`/endpoint in prod.

## 6. Deferred — Phase 2 (owner decision)

- N+1 / payload reduction in `OrderItemSerializer` (nests full product + variant).
- `IsConversationParticipant` on a list endpoint is ineffective (queryset-level).
- Chat: token passed in URL query string (leaks in logs); `Content-Disposition`
  header interpolation of stored `file_name` (header injection); SecureAttachment
  auth by query token.
- Missing unique constraints: `Cart.user` (1:1), `MoneyDectedButOrderFailed.transaction_id`.
- `stale origins` rotation for JWT/refresh; notification/email flows are stubs.
- Chat API tests: 2 failures + environment errors reproduced on clean HEAD
  (`channels_redis` missing locally; one test asserts 201 where the app correctly
  returns 400). Wrap `ChatAPITests` in `@override_settings(CHANNEL_LAYERS=InMemory...)`
  and correct the wrong assertion.

---

## 7. Git history purge (P0) — pending owner confirmation

`.env.dev` is in history (`e738bbd`). `git filter-repo` is available at
`/usr/bin/git-filter-repo`. Recommended one-time step **after** the fix commits:

```bash
git pull --rebase origin main          # sync first
git filter-repo --invert-paths --path .env.dev
git remote add origin git@github.com:mNiloy695/town_market_optimized.git
git push --force origin main           # REQUIRES owner approval (rewrites history)
```

Rotate all exposed credentials **before or immediately after** the force-push.