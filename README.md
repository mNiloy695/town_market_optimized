# Town Market - eCommerce API Documentation

A comprehensive Django REST Framework API for managing products with variants, dynamic options, and a shopping cart system.

---

## Table of Contents
1. [Product APIs](#product-apis)
2. [Cart APIs](#cart-apis)
3. [Request/Response Examples](#requestresponse-examples)
4. [Error Handling](#error-handling)
5. [Frontend Integration](#frontend-integration)

---

## Product APIs

### 1. Get Product Details
**Endpoint:** `GET /v1/product/list/{product_id}/`

**Description:** Fetch product details including all variants, images, and available options with their IDs.

**Response:**
```json
{
  "id": 10,
  "name": "Nike Air Max Professional",
  "slug": "nike-air-max-professional",
  "shop": 13,
  "shop_data": {
    "shop_name": "SALAH TOWER 1",
    "shop_id": 13
  },
  "sub_category": 5,
  "sub_category_data": {
    "sub_category_name": "Suits",
    "sub_category_id": 5
  },
  "variants": [
    {
      "id": 73,
      "price": "150.00",
      "stock": 100,
      "description": "Red Edition / Size XL",
      "option_values": [
        {
          "id": 143,
          "option_value": 9,
          "option_value_data": {
            "option_name": "size",
            "value_id": 9,
            "value_name": "s"
          }
        },
        {
          "id": 144,
          "option_value": 14,
          "option_value_data": {
            "option_name": "color",
            "value_id": 14,
            "value_name": "red"
          }
        }
      ]
    }
  ],
  "available_options": {
    "size": [
      {"id": 9, "value": "s"},
      {"id": 10, "value": "m"},
      {"id": 13, "value": "xxl"}
    ],
    "color": [
      {"id": 14, "value": "red"},
      {"id": 16, "value": "green"}
    ]
  },
  "images": [],
  "created_at": "2026-04-06T08:37:58Z",
  "updated_at": "2026-04-06T08:37:58Z"
}
```

---

### 2. Get Available Options (Filtered)
**Endpoint:** `POST /v1/product/{product_id}/available-options/`

**Description:** Returns available options based on already selected option value IDs. Used for dynamic filtering as user selects options.

**Request:**
```json
{
  "selected_option_value_ids": [13]
}
```
- `13` = ID of "xxl" size (value_id from available_options)

**Response:**
```json
{
  "color": [
    {"id": 14, "value": "red"},
    {"id": 16, "value": "green"}
  ],
  "material": [
    {"id": 20, "value": "cotton"}
  ]
}
```

**Note:** Returns only unselected option groups with their IDs and values.

---

### 3. Find Variant ID
**Endpoint:** `POST /v1/product/{product_id}/find-variant/`

**Description:** Finds the exact variant ID matching the selected option value IDs.

**Request:**
```json
{
  "option_value_ids": [13, 16, 20]
}
```
- `13` = xxl (size)
- `16` = green (color)
- `20` = cotton (material)

**Response:**
```json
{
  "variant_id": 77
}
```

**Error Response:**
```json
{
  "error": "No variant found with the given option values"
}
```

---

### 4. Search Products
**Endpoint:** `GET /v1/product/list/?search=nike&shop__id=13`

**Parameters:**
- `search`: Search by product name, category slug, shop slug
- `shop__id`: Filter by shop ID

**Response:** List of matching products with pagination (20 per page).

---

## Cart APIs

### 1. Add to Cart
**Endpoint:** `POST /v1/cart/add/`

**Authentication:** Required (Bearer token)

**Request:**
```json
{
  "variant_id": 77,
  "quantity": 2
}
```

**Response (201 Created):**
```json
{
  "id": 5,
  "cart": 3,
  "product_variant": 77,
  "product_variant_data": {
    "id": 77,
    "price": "145.00",
    "stock": 45,
    "description": "Blue Edition / Size XL",
    "image": "http://example.com/media/product_images/image.jpg",
    "is_available": true
  },
  "quantity": 2,
  "added_at": "2026-04-06T12:34:56Z",
  "updated_at": "2026-04-06T12:34:56Z"
}
```

**Error Response (400):**
```json
{
  "detail": "Not enough stock."
}
```

**Note:** If variant already in cart, quantity is incremented.

---

### 2. Get Cart Details
**Endpoint:** `GET /v1/cart/detail/`

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "id": 3,
  "user": 1,
  "created_at": "2026-04-06T12:00:00Z",
  "updated_at": "2026-04-06T12:34:56Z",
  "items": [
    {
      "id": 5,
      "cart": 3,
      "product_variant": 77,
      "product_variant_data": {
        "id": 77,
        "price": "145.00",
        "stock": 45,
        "description": "Blue Edition",
        "image": "http://example.com/media/product_images/image.jpg",
        "is_available": true
      },
      "quantity": 2,
      "added_at": "2026-04-06T12:34:56Z",
      "updated_at": "2026-04-06T12:34:56Z"
    }
  ],
  "total": "290.00"
}
```

**Note:** 
- `total` = sum of (variant price × item quantity)
- `is_available` = true if stock >= quantity

---

## Request/Response Examples

### Complete User Flow

#### 1. Load Product Page
```bash
curl -X GET "http://localhost:8000/v1/product/list/10/" \
  -H "Content-Type: application/json"
```

#### 2. User Selects "Size = xxl" (id 13)
```bash
curl -X POST "http://localhost:8000/v1/product/10/available-options/" \
  -H "Content-Type: application/json" \
  -d '{"selected_option_value_ids": [13]}'
```

#### 3. User Selects "Color = green" (id 16)
```bash
curl -X POST "http://localhost:8000/v1/product/10/available-options/" \
  -H "Content-Type: application/json" \
  -d '{"selected_option_value_ids": [13, 16]}'
```

#### 4. Find Variant for "xxl" + "green"
```bash
curl -X POST "http://localhost:8000/v1/product/10/find-variant/" \
  -H "Content-Type: application/json" \
  -d '{"option_value_ids": [13, 16]}'
```

#### 5. Add to Cart
```bash
curl -X POST "http://localhost:8000/v1/cart/add/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your_token" \
  -d '{"variant_id": 77, "quantity": 2}'
```

#### 6. View Cart
```bash
curl -X GET "http://localhost:8000/v1/cart/detail/" \
  -H "Authorization: Token your_token"
```

---

## Error Handling

### Common Errors

| Error | Status | Cause |
|-------|--------|-------|
| `"Not enough stock."` | 400 | Requested quantity exceeds available stock |
| `"Product variant does not exist."` | 400 | Invalid `variant_id` in add to cart |
| `"No variant found with the given option values"` | 400 | Selected options don't match any variant |
| `"Not authenticated"` | 401 | Missing or invalid token for cart APIs |

### Response Format
```json
{
  "detail": "Error message here"
}
```

---

## Frontend Integration

### Key Points

1. **Option IDs are required for filtering:**
   - Get available_options from product endpoint
   - Collect `id` from each selected option
   - Send to available-options and find-variant APIs

2. **Dynamic Filtering:**
   - Call available-options after each user selection
   - Pass accumulated selected_option_value_ids
   - Update UI with remaining options

3. **Stock Handling:**
   - Check `is_available` in cart items
   - Show warnings if not available
   - Prevent checkout if any item unavailable

4. **Image Display:**
   - CartItemSerializer returns first product image URL in `product_variant_data.image`
   - Handle null images gracefully

### Example Frontend Pseudo-code
```javascript
// Step 1: Load product
const product = await fetch(`/v1/product/list/${productId}`)
  .then(r => r.json());

// Show initial options from product.available_options

let selectedIds = [];

// Step 2: On option selection
async function selectOption(optionValueId) {
  selectedIds.push(optionValueId);
  
  // Get filtered options
  const filtered = await fetch(
    `/v1/product/${productId}/available-options/`,
    {
      method: 'POST',
      body: JSON.stringify({ selected_option_value_ids: selectedIds })
    }
  ).then(r => r.json());
  
  // Update UI with filtered options
  updateOptions(filtered);
}

// Step 3: When all options selected
async function addToCart(quantity) {
  // Find variant
  const variant = await fetch(
    `/v1/product/${productId}/find-variant/`,
    {
      method: 'POST',
      body: JSON.stringify({ option_value_ids: selectedIds })
    }
  ).then(r => r.json());
  
  // Add to cart
  const cartItem = await fetch('/v1/cart/add/', {
    method: 'POST',
    headers: { 'Authorization': `Token ${token}` },
    body: JSON.stringify({ 
      variant_id: variant.variant_id, 
      quantity: quantity 
    })
  }).then(r => r.json());
  
  console.log('Item added:', cartItem);
}
```

---

## Authentication

All cart endpoints require token authentication:

```
Authorization: Token your_auth_token
```

Get token via `/v1/accounts/login/` or registration endpoint.

---

## Base URL

```
http://localhost:8000/v1/
```

Replace with your production domain in deployment.

---

## Performance Notes

- Product endpoints use `prefetch_related` to minimize database queries
- Cart total is calculated on-the-fly; consider caching for large carts
- Option filtering is optimized with indexed lookups
- Image URLs are absolute paths; ensure MEDIA_ROOT is properly configured

---

## Support

For issues or questions, check the main `guide.md` for architecture details or open an issue in the repository.
