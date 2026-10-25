"""Pure synthetic dataset generator for DataQuery e-commerce database.

This module contains a pure generator function:
- Completely deterministic based on integer seed (default 42).
- Zero system clock calls (no datetime.now() or datetime.today()).
- Zero environment variable lookups.
- Zero database interactions.
"""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any


def generate_dataset(
    seed: int = 42,
    as_of: date = date(2024, 11, 1),
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic in-memory e-commerce dataset.

    Args:
        seed: Random seed for exact reproducibility.
        as_of: Reference analytical date. All order dates fall within the 12 months up to as_of.

    Returns:
        Dictionary containing lists of dicts for customers, products, orders, order_items, payments.
    """
    rng = random.Random(seed)

    # -------------------------------------------------------------------------
    # 1. Customers (~200 records across 5 regions)
    # -------------------------------------------------------------------------
    # North is deliberately dominant (~35%) so top region has no tie.
    regions = ["North", "South", "East", "West", "Central"]
    region_weights = [0.35, 0.20, 0.18, 0.15, 0.12]

    customers: list[dict[str, Any]] = []
    num_customers = 200
    for cid in range(1, num_customers + 1):
        # Signup dates fall between 400 days and 30 days before as_of
        signup_offset = rng.randint(30, 400)
        signup_date = as_of - timedelta(days=signup_offset)
        region = rng.choices(regions, weights=region_weights, k=1)[0]
        customers.append(
            {
                "id": cid,
                "name": f"Customer {cid:04d}",
                "email": f"customer_{cid:04d}@example.com",
                "region": region,
                "signup_date": signup_date,
            }
        )

    # -------------------------------------------------------------------------
    # 2. Products (~40 products across 7 categories)
    # -------------------------------------------------------------------------
    # Electronics has high unit prices and high sales so top product/category has no ties.
    categories = [
        "Electronics",
        "Apparel",
        "Home & Kitchen",
        "Beauty & Personal Care",
        "Sports & Outdoors",
        "Books",
        "Office Supplies",
    ]

    products: list[dict[str, Any]] = []
    pid = 1
    # Category price ranges (min_price, max_price)
    price_ranges = {
        "Electronics": (80.0, 950.0),
        "Apparel": (15.0, 120.0),
        "Home & Kitchen": (20.0, 250.0),
        "Beauty & Personal Care": (8.0, 75.0),
        "Sports & Outdoors": (25.0, 300.0),
        "Books": (10.0, 45.0),
        "Office Supplies": (5.0, 60.0),
    }

    # Generate 5-6 products per category for ~40 total
    for cat in categories:
        count = 6 if cat in ["Electronics", "Apparel"] else 5
        min_p, max_p = price_ranges[cat]
        for idx in range(1, count + 1):
            if cat == "Electronics" and idx == 1:
                # Deliberate top revenue flagship product: no ties at Rank 1
                price = Decimal("899.99")
                pname = "Flagship Ultra 4K Smart Monitor"
            else:
                raw_price = rng.uniform(min_p, max_p)
                price = Decimal(f"{raw_price:.2f}")
                pname = f"{cat} Item {idx}"
            products.append(
                {
                    "id": pid,
                    "name": pname,
                    "category": cat,
                    "unit_price": price,
                }
            )
            pid += 1

    num_products = len(products)
    product_map = {p["id"]: p for p in products}

    # -------------------------------------------------------------------------
    # 3. Orders (~1500 orders) & Order Items (1-4 items per order)
    # -------------------------------------------------------------------------
    # Status distribution: leaves meaningful undelivered ('placed', 'shipped') and cancelled
    statuses = ["delivered", "shipped", "placed", "cancelled"]
    status_weights = [0.65, 0.15, 0.10, 0.10]

    orders: list[dict[str, Any]] = []
    order_items: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []

    # Customers 195..200 are deliberately given 0 orders (inactive customer tests)
    active_customer_ids = list(range(1, 195))

    num_orders = 1500
    item_id_seq = 1
    payment_id_seq = 1

    for oid in range(1, num_orders + 1):
        # Customer 1 is given higher probability so "top customer by spend" has no tie
        if rng.random() < 0.05:
            customer_id = 1
        else:
            customer_id = rng.choice(active_customer_ids)

        # Order date: spread uniformly over the 365 days ending at as_of
        days_back = rng.randint(0, 364)
        order_date = as_of - timedelta(days=days_back)
        status = rng.choices(statuses, weights=status_weights, k=1)[0]

        orders.append(
            {
                "id": oid,
                "customer_id": customer_id,
                "order_date": order_date,
                "status": status,
            }
        )

        # 1-4 items per order
        # Customer 1 gets 3-4 items including Flagship Electronics (pid=1) frequently
        if customer_id == 1:
            num_items = rng.randint(2, 4)
        else:
            num_items = rng.randint(1, 4)

        chosen_pids = rng.sample(range(1, num_products + 1), k=num_items)
        if customer_id == 1 and 1 not in chosen_pids:
            chosen_pids[0] = 1

        order_total = Decimal("0.00")
        for p_id in chosen_pids:
            prod = product_map[p_id]
            # Flagship product gets higher quantities on customer 1
            qty = rng.randint(1, 3) if customer_id != 1 else rng.randint(2, 4)
            unit_price = prod["unit_price"]
            line_total = Decimal(qty) * unit_price
            order_total += line_total

            order_items.append(
                {
                    "id": item_id_seq,
                    "order_id": oid,
                    "product_id": p_id,
                    "quantity": qty,
                    "unit_price": unit_price,
                }
            )
            item_id_seq += 1

        # ---------------------------------------------------------------------
        # 4. Payments (matching order totals)
        # ---------------------------------------------------------------------
        # Payment status aligns with order status
        payment_methods = ["credit_card", "paypal", "bank_transfer", "debit_card"]
        method = rng.choice(payment_methods)

        if status == "cancelled":
            p_status = rng.choice(["refunded", "failed"])
            paid_at = datetime(order_date.year, order_date.month, order_date.day, 12, 0, 0)
        else:
            p_status = "completed"
            paid_at = datetime(
                order_date.year, order_date.month, order_date.day, 12, 0, 0
            ) + timedelta(minutes=rng.randint(1, 120))

        payments.append(
            {
                "id": payment_id_seq,
                "order_id": oid,
                "amount": order_total,
                "method": method,
                "status": p_status,
                "paid_at": paid_at,
            }
        )
        payment_id_seq += 1

    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
    }
