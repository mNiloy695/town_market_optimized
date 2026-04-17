# 🚀 Town Market - Complete eCommerce API Documentation

A professional, production-ready multi-vendor e-commerce backend built with Django REST Framework. This system supports independent shop management, product variants with dynamic options, thread-safe stock reservation, and a split-payment (Booking Fee + COD) checkout flow.

---

## 🛠️ Global Configuration

- **Base URL**: `http://<domain>/v1/`
- **Content-Type**: `application/json`
- **Authentication**: JWT (JSON Web Token)
- **Header**: `Authorization: Bearer <token>`

---

## 🔑 1. Authentication & Accounts

### Registration & Login
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `accounts/auth/registration/` | `POST` | Register with `phone`, `password`, `name`. Sends OTP. |
| `accounts/auth/active/` | `POST` | Activate account using `phone` and 4-digit `otp`. |
| `accounts/auth/login/` | `POST` | Login to get `access` and `refresh` tokens. |
| `accounts/auth/token/refresh/` | `POST` | Refresh expired access tokens. |
| `accounts/auth/profile/` | `GET` | Get current user profile details. |

---

## 🏬 2. Shop Management

### Shop Discovery
- **List Shops**: `GET /v1/shop/list/` (Paginated)
- **Shop Detail**: `GET /v1/shop/list/{id}/`

### Vendor Onboarding
- **Apply for Shop**: `POST /v1/shop/request/`
- **Format**: `multipart/form-data`
- **Fields**: `name`, `logo` (Image), `cover_image` (Image), `description`.

---

## 📦 3. Product Catalog & Variants

### Product List & Search
- **Endpoint**: `GET /v1/product/list/`
- **Filters**: `search`, `category` (ID), `shop` (ID).
- **Includes**: `variants`, `images`, `average_rating`, `eligibale_for_review`.

### Dynamic Option Filtering (Crucial for Frontend)
As a user selects options (e.g., Color), the UI should update available sizes that actually exist in stock.

1. **Get Initial Available Options**: From the product detail response (`available_options` field).
2. **Filter After Selection**: `POST /v1/product/{id}/available-options/`
   - Request: `{ "selected_option_value_ids": [id1, id2] }`
   - Response: Returns remaining valid combinations.
3. **Find Exact Variant**: `POST /v1/product/{id}/find-variant/`
   - Request: `{ "option_value_ids": [id1, id2] }`
   - Response: `{ "variant_id": 77 }`

---

## 🛒 4. Cart & Stock Reservation

### Real-Time Reservation
When a user adds an item to the cart, the system **locks** the stock for a limited time to prevent overselling.

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `cart/add/` | `POST` | Add `variant_id` and `quantity`. Reserves stock. |
| `cart/detail/` | `GET` | View cart with `item_total`, `shipping_total`, and `booking_amount`. |
| `cart/remove/item/{variant_id}/` | `DELETE`| Remove item and release stock. |

---

## 💳 5. Checkout & Partial Payments (SSLCommerz)

### Split-Payment Workflow
Town Market uses a **Booking Fee + Cash on Delivery** model.
- **Booking Fee**: Total Shipping Fee (paid upfront via SSLCommerz).
- **Remaining Balance**: Paid to the courier upon delivery (COD).

### The Checkout Process
1. **Initiate Checkout**: `POST /v1/order/checkout/`
   - Body: `shipping_address`, `shipping_city` (e.g., feni), `shipping_upazilla`, `phone_number`.
   - Response: Returns a `payment_url`.
2. **Payment Redirection**: Redirect user to the `payment_url`.
3. **Webhook Confirmation**: Our backend receives an IPN from SSLCommerz.
   - **Cart is auto-cleared** on success.
   - Order status moves to `confirmed`.
4. **Retry Payment**: If payment fails, use `POST /v1/order/{id}/pay-now/`.

---

## ⭐ 6. Reviews & Ratings

- **List Reviews**: `GET /v1/review/?product_id={id}`
- **Create Review**: `POST /v1/review/`
  - **Rule**: User must have a `delivered` purchase for this product.
  - **Feature**: If `review_text` is empty, system generates default text (e.g., 5-stars → "I am extremely satisfied...").
  - **Response**: Includes `rating` and `rating_display` (emoji stars).

---

## 🛡️ Role-Based Access

| Role | Permissions |
| :--- | :--- |
| **Buyer** | Create orders, manage cart, leave reviews. |
| **Seller** | Manage own shop products, process orders, approve returns. |
| **Admin** | Full system access, category management, shop approval. |

### Vendor (Seller) Dashboard Endpoints
- **My Products**: `GET /v1/product/vendor/my-shop-product/`
- **Shop Orders**: `GET /v1/order/vendor/orders/`
- **Update Status**: `PATCH /v1/order/vendor/orders/{id}/status/` (pending → confirmed → shipped → delivered).
- **Return Approval**: `PATCH /v1/order/vendor/orders/{id}/return-approval/` (`approve` or `reject`).

---

## 🧪 Developer Support
- **Error Format**: All errors return `{ "detail": "message" }` or `{ "field_name": ["error"] }`.
- **Status Codes**: 200 (Success), 201 (Created), 400 (Validation Error), 401 (Auth Error), 403 (Permission Denied).
