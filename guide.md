# ECommerce Product Variant & Cart System Guide

## Overview
This system implements a robust product variant management, option selection, and cart functionality similar to Shopify/Amazon. Products have multiple options (e.g., Size, Color), each variant represents a unique combination, and the cart stores variant IDs with quantities.

## Key Features
- **Variant Management**: Unique combinations of options with price, stock, description.
- **Dynamic Options**: Frontend sees grouped options, not raw variants.
- **Cart System**: Stores variant_id and quantity, derives price/stock from variant.
- **Validation**: Ensures no duplicate variants, valid combinations only.

## Data Models

### Product
- name, slug, shop, sub_category
- Has many ProductVariant

### ProductVariant
- product (FK), price, stock, description
- Has many ProductVariantOptionValue

### ProductVariantOptionValue
- variant (FK), option_value (FK)
- Links variant to specific option values

### Cart
- user (FK), created_at, updated_at
- Has many CartItem

### CartItem
- cart (FK), product_variant (FK), quantity, added_at, updated_at
- Unique together: (cart, product_variant)

## API Endpoints

### Product APIs
1. **GET /v1/product/list/{id}/**
   - Returns product details + `available_options` (grouped options for frontend)
   - Example Response:
     ```json
     {
       "id": 1,
       "name": "T-Shirt",
       "available_options": {
         "Size": [
           {"id": 9, "value": "S"},
           {"id": 10, "value": "M"}
         ],
         "Color": [
           {"id": 14, "value": "Red"},
           {"id": 16, "value": "Blue"}
         ]
       }
     }
     ```

2. **POST /v1/product/{id}/available-options/**
   - Returns filtered options based on selected option value IDs
   - Request: `{"selected_option_value_ids": [9, 14]}`
   - Example Response: 
     ```json
     {
       "Material": [
         {"id": 20, "value": "Cotton"}
       ]
     }
     ```

3. **POST /v1/product/{id}/find-variant/**
   - Finds variant_id from selected option value IDs
   - Request: `{"option_value_ids": [9, 14]}`
   - Response: `{"variant_id": 12}`

### Cart APIs
1. **POST /v1/cart/add/**
   - Adds item to cart
   - Request: `{"variant_id": 12, "quantity": 2}`
   - Response: Cart item details with variant data (price, stock, image)

2. **GET /v1/cart/detail/**
   - Returns user's cart with items, total price
   - Response includes `total` (sum of item prices * quantities)
   - Each item includes `is_available` (true if stock >= quantity)

## Frontend Flow

### 1. Display Product
- Fetch product details via `GET /v1/product/list/{id}/`
- Display product info + option selectors (dropdowns/buttons) from `available_options`

### 2. Handle Option Selection
- When user selects an option (e.g., Size = xxl with id 13):
  - Call `POST /v1/product/{id}/available-options/` with `{"selected_option_value_ids": [13]}`
  - Update remaining option selectors with filtered values
- Repeat for each selection until all options chosen

### 3. Add to Cart
- Once all options selected (e.g., Size=M, Color=Red):
  - Collect the `option_value` IDs from the selected values
  - Call `POST /v1/product/{id}/find-variant/` with `{"option_value_ids": [9, 14]}`
  - Get `variant_id` from response
  - Call `POST /v1/cart/add/` with `variant_id` and `quantity`

### 4. View Cart
- Call `GET /v1/cart/detail/` to show items with images, prices, quantities, and total

## Validation & Rules
- Variants must have unique option combinations per product
- Only in-stock variants shown in options
- Cart checks stock before adding
- Options filtered dynamically based on availability

## Example Usage

### Create Product with Variants
- POST to `/v1/product/list/` with nested variants and option_values

### Frontend Example
```javascript
// Load product
fetch('/v1/product/list/1/')
  .then(res => res.json())
  .then(data => {
    // Display options: data.available_options
  });

// On select Size=xxl (id 13)
fetch('/v1/product/1/available-options/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({selected_option_value_ids: [13]})
})
.then(res => res.json())
.then(options => {
  // Update Color dropdown with options.Color
});

// Add to cart
fetch('/v1/product/1/find-variant/', {
  method: 'POST',
  body: JSON.stringify({option_value_ids: [9, 14]})
})
.then(res => res.json())
.then(data => {
  return fetch('/v1/cart/add/', {
    method: 'POST',
    body: JSON.stringify({variant_id: data.variant_id, quantity: 1})
  });
});
```

## Performance Notes
- Use `select_related`/`prefetch_related` for option values
- Cache option groupings if needed
- Index on variant option lookups

## Next Steps
- Implement order placement from cart
- Add wishlist functionality
- Integrate with payment gateways