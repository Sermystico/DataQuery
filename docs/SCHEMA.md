# Database Schema & Data Architecture Specification

## 1. Overview & Schemas

The DataQuery database (`dataquery_dev`) is structured into two dedicated schemas:

1. **`public`**: Contains all business domain analytics tables (`customers`, `products`, `orders`, `order_items`, `payments`). Accessible to `dq_readonly` for query generation and execution.
2. **`app`**: Dedicated schema for internal application metadata (e.g., query audit logs, execution metrics, user sessions). Strictly isolated from `dq_readonly` and accessible only by `dq_app` and `dq_owner`.

---

## 2. Table Specifications & Column Dictionary

### 2.1. `public.customers`
Represents registered customer accounts and their geographic classification.

| Column | Type | Nullable | Default / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `NO` | Primary Key, Autoincrement | Unique customer identifier |
| `name` | `TEXT` | `NO` | | Full customer display name (e.g. `Customer 0001`) |
| `email` | `TEXT` | `NO` | `UNIQUE` | Unique contact email address |
| `region` | `TEXT` | `NO` | | Geographic market (`North`, `South`, `East`, `West`, `Central`) |
| `signup_date`| `DATE` | `NO` | | Date the customer created their account |

---

### 2.2. `public.products`
The merchandise catalog available for purchase, including categorization and pricing.

| Column | Type | Nullable | Default / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `NO` | Primary Key, Autoincrement | Unique product identifier |
| `name` | `TEXT` | `NO` | | Product title / description |
| `category` | `TEXT` | `NO` | | Merchandising category (`Electronics`, `Apparel`, etc.) |
| `unit_price` | `NUMERIC(10,2)`| `NO` | `CHECK (unit_price > 0)` | Standard listing price in USD |

---

### 2.3. `public.orders`
Transaction headers capturing purchase requests and order fulfillment lifecycle states.

| Column | Type | Nullable | Default / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `NO` | Primary Key, Autoincrement | Unique order identifier |
| `customer_id`| `INTEGER` | `NO` | `FK -> customers(id)` | Purchasing customer reference |
| `order_date` | `DATE` | `NO` | | Date order was submitted |
| `status` | `TEXT` | `NO` | `CHECK (status IN ('placed', 'shipped', 'delivered', 'cancelled'))` | Fulfillment status |

---

### 2.4. `public.order_items`
Line item details for each order, capturing quantities and the historical price at point of sale.

| Column | Type | Nullable | Default / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `NO` | Primary Key, Autoincrement | Unique line item identifier |
| `order_id` | `INTEGER` | `NO` | `FK -> orders(id)` | Parent purchase order reference |
| `product_id` | `INTEGER` | `NO` | `FK -> products(id)` | Purchased catalog product reference |
| `quantity` | `INTEGER` | `NO` | `CHECK (quantity > 0)` | Number of units purchased |
| `unit_price` | `NUMERIC(10,2)`| `NO` | `CHECK (unit_price > 0)` | Price per unit at purchase time |

---

### 2.5. `public.payments`
Financial transaction records capturing customer billing for submitted orders.

| Column | Type | Nullable | Default / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `NO` | Primary Key, Autoincrement | Unique payment transaction identifier |
| `order_id` | `INTEGER` | `NO` | `FK -> orders(id)` | Associated order reference |
| `amount` | `NUMERIC(12,2)`| `NO` | | Total billed payment amount in USD |
| `method` | `TEXT` | `NO` | | Payment channel (`credit_card`, `paypal`, `bank_transfer`, `debit_card`) |
| `status` | `TEXT` | `NO` | | Settlement state (`completed`, `refunded`, `failed`) |
| `paid_at` | `TIMESTAMP` | `YES` | | Timestamp of payment transaction execution |

---

## 3. Index Strategy & Justifications

To ensure natural language analytical queries complete well within our 3,000ms `statement_timeout`, explicit B-tree indexes are created for frequent join and filter paths:

1. **`ix_orders_customer_id` on `orders(customer_id)`**:
   - *Query Pattern*: Joins between `customers` and `orders` (`customers c JOIN orders o ON c.id = o.customer_id`).
   - *Justification*: Prevents expensive sequential scans on `orders` when aggregating customer order volume, calculating individual customer lifetime spend, or filtering inactive customers.
2. **`ix_orders_order_date` on `orders(order_date)`**:
   - *Query Pattern*: Date-range filtering and temporal aggregations (`WHERE order_date >= '2024-10-01' AND order_date < '2024-11-01'`).
   - *Justification*: Time-series and relative date queries ("last 30 days", "orders in Q3") perform index range scans instead of reading all order rows.
3. **`ix_order_items_order_id` on `order_items(order_id)`**:
   - *Query Pattern*: Joins connecting `orders` to `order_items` (`orders o JOIN order_items oi ON o.id = oi.order_id`).
   - *Justification*: `order_items` is the largest table in the database (~4,000 rows). Joining header to line items is required for almost all revenue queries.
4. **`ix_order_items_product_id` on `order_items(product_id)`**:
   - *Query Pattern*: Product-level aggregations (`GROUP BY product_id`, `JOIN products p ON oi.product_id = p.id`).
   - *Justification*: Essential for top-selling product queries ("Top 5 products by quantity sold", "Product revenue breakdown").

---

## 4. Three-Role Database Security Model

PostgreSQL role architecture adheres strictly to the **Principle of Least Privilege**:

```
                  ┌────────────────────────┐
                  │        dq_owner        │
                  │  (Migrations & DDL)    │
                  └───────────┬────────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│       dq_readonly       │       │         dq_app          │
│ (Analytics LLM Queries) │       │   (Application State)   │
├─────────────────────────┤       ├─────────────────────────┤
│ • SELECT on 5 tables    │       │ • USAGE on 'app' schema │
│ • read_only = on        │       │ • Zero analytics access │
│ • timeout = 3000ms      │       │ • No CREATE privileges  │
│ • No access to 'app'    │       │                         │
└─────────────────────────┘       └─────────────────────────┘
```

### Role Breakdown:
1. **`dq_owner`**:
   - Schema and table owner.
   - Executes Alembic migrations and seed loading scripts.
   - Manages default privileges and access grants.
2. **`dq_readonly`**:
   - Connection role used exclusively when executing SQL generated by the LLM.
   - Granted `SELECT` only on `customers`, `products`, `orders`, `order_items`, `payments`.
   - Explicitly denied access to `app` schema and system catalog tables (`pg_shadow`, `pg_authid`).
   - Hardened with PostgreSQL session defaults:
     `SET default_transaction_read_only = on;`
     `SET statement_timeout = '3000ms';`
3. **`dq_app`**:
   - Connection role for backend application services (e.g. writing to `app.query_history`).
   - Granted `USAGE` on schema `app`.
   - Denied access to public analytics tables.

---

## 5. Domain Rules & Business Logic Definitions

All analytical queries and evaluation benchmarks adhere to these technical definitions:

- **Revenue**:
  $$\text{Revenue} = \sum (\text{order\_items.quantity} \times \text{order\_items.unit\_price}) \quad \text{WHERE } \text{orders.status} \ne \text{'cancelled'}$$
  *Cancelled orders contribute \$0 to revenue. Delivered, placed, and shipped orders count toward total revenue.*
- **Undelivered Orders**:
  $$\text{status} \in (\text{'placed'}, \text{'shipped'})$$
  *Orders with status 'delivered' or 'cancelled' are excluded.*
- **Customer Region**:
  Mapped directly from `customers.region` (`North`, `South`, `East`, `West`, `Central`).
- **Fixed Analytical Reference Date**:
  $$\text{ANALYTICS\_AS\_OF\_DATE} = \text{'2024-11-01'}$$
  *Guarantees reproducible relative date evaluations ("last 30 days", "orders this month").*
