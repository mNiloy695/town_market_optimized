🔄 How the Flow Works Now:
Step 1: List main categories via /product/parent-product-category/.
Step 2: List subcategories for a selected parent via /product/product-category/?parent__slug=SLUG.
Step 3: Get available options (Size, Color, etc.) for a subcategory via /product/product-category-option/?product_category__id=ID.
Step 4: When an option is clicked, the app shows listing values for that option.
Step 5: Once a value is selected, the user creates a 

ProductVariant
 with its own price and description.
Multi-variants: Tapping the "+" icon simply starts a new 

ProductVariant
 creation cycle, allowing multiple variants for the same product.
The database migrations have been generated and applied. You are ready to integrate this with your frontend!


✅ Active APIs (Keep these)
/product/product/: (GET/POST) The primary endpoint for creating/listing products with all variants included.
/product/parent-product-category/: (GET) To select the main category.
/product/product-category/: (GET) To filter and select sub-categories.
/product/product-category-option/: (GET) To get options (Size, Color) for a sub-category.
/product/product-category-option-value/: (GET) To get specific values (Red, XL).