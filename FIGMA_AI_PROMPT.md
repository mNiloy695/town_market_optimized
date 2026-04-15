# Figma AI Prompt: Dynamic Product & Variant Management Flow

## Overview
Design a comprehensive product management interface that allows shop owners to add new products and dynamically manage their variations (variants) based on category-specific options. The system uses a flexible option-based variant structure where products inherit customizable attributes from their category.

---

## Data Model Context

### Product Hierarchy
```
Shop
├── Product (name, slug, images)
│   └── Category (inherited from product)
│       └── Category Options (e.g., Size, Color, Material)
│           └── Option Values (e.g., S/M/L for Size, Red/Blue for Color)
└── Variants (price, stock, description + option combinations)
     └── Each variant = specific combination of option values
```

### Key Relationships
- **Product** → belongs to 1 Shop + 1 Category
- **Category** → has predefined Options
- **Variant** → represents unique combination of Option Values with its own price & stock
- **Images** → multiple per product, used for all variants

---

## UI Flow: Add Product

### Step 1: Basic Product Information
- **Product Name** (text input)
- **Slug** (auto-generated, editable)
- **Select Category** (dropdown → loads that category's available options)
- **Product Images** (multi-file upload → draggable preview gallery)

### Step 2: Variant Configuration Setup
After selecting category, display:
- **Available Options for this Category** (e.g., "Size", "Color", "Material")
- For each option, show **all possible values** in chips/toggles
  - User selects which values apply to this product
  - Example: For T-shirt in "Clothing" category → select Size options [S, M, L] + Color options [Red, Blue]

### Step 3: Variant Management (Dynamic Grid)
**Display a table/grid of all possible variant combinations:**
- Columns: 
  - Variant ID
  - Option Value Combination (e.g., "S - Red", "M - Blue")
  - Price (input)
  - Stock (input)
  - Description (text area/"View" button)
  - Actions (Edit/Delete)

**Variants Generated**: 
- If Size [S, M, L] + Color [Red, Blue] selected → 6 variants auto-generated
- Pre-populate with empty values, user fills in price & stock

**Dynamic Features**:
- Add/Remove rows by changing option selections (update combinations in real-time)
- Quick-fill: "Apply price to all" / "Set same stock" buttons
- Show variant count: "6 of 6 variants configured"

### Step 4: Review & Publish
- Summary card showing:
  - Product name, category, image count
  - Total variants count
  - Price range (min-max across all variants)
  - All variants quick preview
- **Create Product** button → saves product + all variants + images

---

## UI Flow: Update Product

### Product Detail Page
**Header Section**:
- Product name (editable)
- Product images (manage gallery - add/remove/reorder)
- Category (read-only or allow category change if validated)

**Variant Management Section** (Main Editor):

#### Quick Stats
- Total variants: X
- Configured variants: Y
- Stock low warnings (if any variant < 5 units)

#### Variant Grid/Table with:
- **In-line Editing** for:
  - Price (decimal input)
  - Stock (integer input)  
  - Description (quick-edit or modal)
  
- **Batch Operations**:
  - Select multiple variants → bulk price update / bulk stock update
  - Delete multiple variants
  
- **Add New Variants**:
  - If category options are added later, show "Add option value combinations" button
  - Dynamically insert new variant rows

#### Variant Actions (Per Row)
- Edit details (modal with full form)
- Delete variant
- Copy variant (duplicate for quick setup)
- Archive variant (soft delete visibility)

#### Dynamic Option Management
- Show current option combinations used
- Option to add/remove specific option values
  - When removed: variants using that value are soft-deleted or marked as unavailable
  - Warning: "3 variants use 'XXL Size' - removing will hide them"

---

## Interaction Patterns

### Dynamic Combination Updates
When user toggles option values (Step 2):
1. Recalculate all possible combinations
2. **Preserve existing data**: Keep price/stock for matching variants
3. **Mark new variants**: New combinations created → show as "New" badge
4. **Remove old variants**: Combinations no longer valid → move to archive or delete confirmation

### Real-time Validation
- Warn if variant combinations duplicate
- Require at least price + stock for publish
- Validate option value belongs to correct category

### State Management Color Coding
- ✅ Configured variant (green border)
- ⚠️ Incomplete variant (yellow border - missing price or stock)
- ❌ Archived variant (gray, strikethrough)

---

## Form Components Needed

1. **Category Selector** with Option Display
2. **Multi-variant Editor Table/Grid**
3. **Bulk Action Toolbar**
4. **Image Gallery Manager**
5. **Option Value Chips/Toggles**
6. **Modal for Variant Details**
7. **Conflict Resolution Dialog** (for removing options used in variants)
8. **Variant Summary Card**

---

## Mobile Responsiveness
- **Desktop**: Full variant table with inline editing
- **Tablet**: Stacked variant cards, collapsible sections
- **Mobile**: 
  - Variant list (name + price + stock visible)
  - Tap to expand for full editing
  - Bulk actions in overflow menu

---

## Design Considerations

### Visual Hierarchy
- Highlight: Configured vs incomplete variants
- Option combinations should be clearly readable
- Price & stock fields prominent
- Actions menu (three dots) for less common operations

### Accessibility
- Keyboard navigation for variant table
- Clear labels for all inputs
- Informative validation messages
- ARIA labels for dynamic content

### Performance
- Virtualization for many variants (1000+)
- Debounce price/stock input updates
- Lazy load images

---

## Additional Features to Consider

1. **Variant Preview**: Show mock card with selected options + price
2. **Stock Warnings**: Visual alerts for low stock variants
3. **Pricing Tiers**: Bulk discount rules by quantity
4. **Variant Search**: Quick find specific variant by option combination
5. **Export/Import**: Bulk variant data export to CSV + import
6. **Variant Templates**: Save configuration as template for future products

