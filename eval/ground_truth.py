"""Independent ground-truth calculations for DataQuery analytical evaluation.

CRITICAL REQUIREMENT:
All expected values are computed purely in Python using `seed.dataset.generate_dataset()`.
The SQL under test is NEVER executed to produce or verify expected ground-truth answers.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from seed.dataset import generate_dataset


def compute_ground_truth(
    seed: int = 42,
    as_of: date = date(2024, 11, 1),
) -> dict[str, dict[str, Any]]:
    """Compute exact expected columns and rows for all golden correctness queries purely in Python."""
    data = generate_dataset(seed=seed, as_of=as_of)

    customers = data["customers"]
    products = data["products"]
    orders = data["orders"]
    order_items = data["order_items"]
    payments = data["payments"]

    # Pre-indexed lookups
    cust_map = {c["id"]: c for c in customers}
    prod_map = {p["id"]: p for p in products}
    non_cancelled_order_ids = {o["id"] for o in orders if o["status"] != "cancelled"}
    order_to_cust_non_cancelled = {
        o["id"]: o["customer_id"] for o in orders if o["status"] != "cancelled"
    }

    results: dict[str, dict[str, Any]] = {}

    # -------------------------------------------------------------------------
    # AGG-01: Total revenue across completed (non-cancelled) orders
    # -------------------------------------------------------------------------
    agg_01_rev = sum(
        Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
        for item in order_items
        if item["order_id"] in non_cancelled_order_ids
    )
    results["AGG-01"] = {
        "columns": ["total_revenue"],
        "rows": [[float(round(agg_01_rev, 2))]],
    }

    # -------------------------------------------------------------------------
    # AGG-02: Average order value for delivered orders
    # -------------------------------------------------------------------------
    delivered_order_ids = {o["id"] for o in orders if o["status"] == "delivered"}
    delivered_totals: dict[int, Decimal] = defaultdict(Decimal)
    for item in order_items:
        if item["order_id"] in delivered_order_ids:
            delivered_totals[item["order_id"]] += Decimal(str(item["quantity"])) * Decimal(
                str(item["unit_price"])
            )
    agg_02_avg = (
        sum(delivered_totals.values()) / Decimal(len(delivered_totals))
        if delivered_totals
        else Decimal("0")
    )
    results["AGG-02"] = {
        "columns": ["average_order_value"],
        "rows": [[float(round(agg_02_avg, 2))]],
    }

    # -------------------------------------------------------------------------
    # AGG-03: Total items purchased across all non-cancelled orders
    # -------------------------------------------------------------------------
    agg_03_items = sum(
        item["quantity"]
        for item in order_items
        if item["order_id"] in non_cancelled_order_ids
    )
    results["AGG-03"] = {
        "columns": ["total_items"],
        "rows": [[agg_03_items]],
    }

    # -------------------------------------------------------------------------
    # AGG-04: Minimum and maximum product price in catalog
    # -------------------------------------------------------------------------
    prices = [Decimal(str(p["unit_price"])) for p in products]
    results["AGG-04"] = {
        "columns": ["min_price", "max_price"],
        "rows": [[float(min(prices)), float(max(prices))]],
    }

    # -------------------------------------------------------------------------
    # AGG-05: Unique customers who have placed at least one non-cancelled order
    # -------------------------------------------------------------------------
    active_customers = {o["customer_id"] for o in orders if o["status"] != "cancelled"}
    results["AGG-05"] = {
        "columns": ["active_customer_count"],
        "rows": [[len(active_customers)]],
    }

    # -------------------------------------------------------------------------
    # AGG-06: Total amount of all successful payments
    # -------------------------------------------------------------------------
    successful_payments = sum(
        Decimal(str(p["amount"])) for p in payments if p["status"] == "completed"
    )
    results["AGG-06"] = {
        "columns": ["total_successful_payments"],
        "rows": [[float(round(successful_payments, 2))]],
    }

    # -------------------------------------------------------------------------
    # GRP-01: Total revenue by customer region
    # -------------------------------------------------------------------------
    region_rev: dict[str, Decimal] = defaultdict(Decimal)
    for item in order_items:
        oid = item["order_id"]
        if oid in order_to_cust_non_cancelled:
            cid = order_to_cust_non_cancelled[oid]
            reg = cust_map[cid]["region"]
            region_rev[reg] += Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
    sorted_grp_01 = sorted(region_rev.items(), key=lambda x: (-x[1], x[0]))
    results["GRP-01"] = {
        "columns": ["region", "total_revenue"],
        "rows": [[reg, float(round(rev, 2))] for reg, rev in sorted_grp_01],
    }

    # -------------------------------------------------------------------------
    # GRP-02: Total number of orders by fulfillment status
    # -------------------------------------------------------------------------
    status_counts = Counter(o["status"] for o in orders)
    sorted_grp_02 = sorted(status_counts.items(), key=lambda x: (-x[1], x[0]))
    results["GRP-02"] = {
        "columns": ["status", "order_count"],
        "rows": [[s, cnt] for s, cnt in sorted_grp_02],
    }

    # -------------------------------------------------------------------------
    # GRP-03: Average product unit price in each category
    # -------------------------------------------------------------------------
    cat_prices: dict[str, list[Decimal]] = defaultdict(list)
    for p in products:
        cat_prices[p["category"]].append(Decimal(str(p["unit_price"])))
    cat_avg = {
        cat: round(sum(p_list) / Decimal(len(p_list)), 2) for cat, p_list in cat_prices.items()
    }
    sorted_grp_03 = sorted(cat_avg.items(), key=lambda x: (-x[1], x[0]))
    results["GRP-03"] = {
        "columns": ["category", "avg_unit_price"],
        "rows": [[cat, float(avg)] for cat, avg in sorted_grp_03],
    }

    # -------------------------------------------------------------------------
    # GRP-04: Categories with revenue > $10,000
    # -------------------------------------------------------------------------
    cat_rev: dict[str, Decimal] = defaultdict(Decimal)
    for item in order_items:
        if item["order_id"] in non_cancelled_order_ids:
            cat = prod_map[item["product_id"]]["category"]
            cat_rev[cat] += Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
    cat_rev_filtered = [(cat, rev) for cat, rev in cat_rev.items() if rev > Decimal("10000")]
    sorted_grp_04 = sorted(cat_rev_filtered, key=lambda x: (-x[1], x[0]))
    results["GRP-04"] = {
        "columns": ["category", "total_revenue"],
        "rows": [[cat, float(round(rev, 2))] for cat, rev in sorted_grp_04],
    }

    # -------------------------------------------------------------------------
    # GRP-05: Customer count by region
    # -------------------------------------------------------------------------
    cust_region_counts = Counter(c["region"] for c in customers)
    sorted_grp_05 = sorted(cust_region_counts.items(), key=lambda x: (-x[1], x[0]))
    results["GRP-05"] = {
        "columns": ["region", "customer_count"],
        "rows": [[reg, cnt] for reg, cnt in sorted_grp_05],
    }

    # -------------------------------------------------------------------------
    # GRP-06: Total amount and payment count by payment method
    # -------------------------------------------------------------------------
    method_stats: dict[str, list[Any]] = defaultdict(lambda: [Decimal("0"), 0])
    for p in payments:
        method_stats[p["method"]][0] += Decimal(str(p["amount"]))
        method_stats[p["method"]][1] += 1
    sorted_grp_06 = sorted(method_stats.items(), key=lambda x: (-x[1][0], x[0]))
    results["GRP-06"] = {
        "columns": ["method", "total_amount", "payment_count"],
        "rows": [[m, float(round(s[0], 2)), s[1]] for m, s in sorted_grp_06],
    }

    # -------------------------------------------------------------------------
    # TOP-01: Top 5 best-selling products by quantity
    # -------------------------------------------------------------------------
    prod_qty: dict[int, int] = defaultdict(int)
    for item in order_items:
        if item["order_id"] in non_cancelled_order_ids:
            prod_qty[item["product_id"]] += item["quantity"]
    sorted_top_01 = sorted(
        prod_qty.items(), key=lambda x: (-x[1], prod_map[x[0]]["name"])
    )[:5]
    results["TOP-01"] = {
        "columns": ["name", "total_quantity"],
        "rows": [[prod_map[pid]["name"], qty] for pid, qty in sorted_top_01],
    }

    # -------------------------------------------------------------------------
    # TOP-02: Top 3 customers by total spend
    # -------------------------------------------------------------------------
    cust_spend: dict[int, Decimal] = defaultdict(Decimal)
    for item in order_items:
        oid = item["order_id"]
        if oid in order_to_cust_non_cancelled:
            cid = order_to_cust_non_cancelled[oid]
            cust_spend[cid] += Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
    sorted_top_02 = sorted(
        cust_spend.items(), key=lambda x: (-x[1], cust_map[x[0]]["name"])
    )[:3]
    results["TOP-02"] = {
        "columns": ["name", "total_spend"],
        "rows": [[cust_map[cid]["name"], float(round(spend, 2))] for cid, spend in sorted_top_02],
    }

    # -------------------------------------------------------------------------
    # TOP-03: Single most expensive product
    # -------------------------------------------------------------------------
    sorted_top_03 = sorted(
        products, key=lambda p: (-Decimal(str(p["unit_price"])), p["name"])
    )[0]
    results["TOP-03"] = {
        "columns": ["name", "unit_price"],
        "rows": [[sorted_top_03["name"], float(sorted_top_03["unit_price"])]],
    }

    # -------------------------------------------------------------------------
    # TOP-04: Top 3 product categories by revenue
    # -------------------------------------------------------------------------
    sorted_top_04 = sorted(cat_rev.items(), key=lambda x: (-x[1], x[0]))[:3]
    results["TOP-04"] = {
        "columns": ["category", "total_revenue"],
        "rows": [[cat, float(round(rev, 2))] for cat, rev in sorted_top_04],
    }

    # -------------------------------------------------------------------------
    # TOP-05: 5 most recent orders placed
    # -------------------------------------------------------------------------
    sorted_top_05 = sorted(
        orders, key=lambda o: (o["order_date"], o["id"]), reverse=True
    )[:5]
    results["TOP-05"] = {
        "columns": ["id", "customer_id", "order_date", "status"],
        "rows": [
            [o["id"], o["customer_id"], o["order_date"].isoformat(), o["status"]]
            for o in sorted_top_05
        ],
    }

    # -------------------------------------------------------------------------
    # DAT-01: Revenue in October 2024
    # -------------------------------------------------------------------------
    oct_orders = {
        o["id"]
        for o in orders
        if o["status"] != "cancelled" and date(2024, 10, 1) <= o["order_date"] < date(2024, 11, 1)
    }
    oct_rev = sum(
        Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
        for item in order_items
        if item["order_id"] in oct_orders
    )
    results["DAT-01"] = {
        "columns": ["total_revenue"],
        "rows": [[float(round(oct_rev, 2))]],
    }

    # -------------------------------------------------------------------------
    # DAT-02: Orders in last 30 days (2024-10-02 to 2024-11-01)
    # -------------------------------------------------------------------------
    d30_orders = sum(
        1 for o in orders if date(2024, 10, 2) <= o["order_date"] <= date(2024, 11, 1)
    )
    results["DAT-02"] = {
        "columns": ["order_count"],
        "rows": [[d30_orders]],
    }

    # -------------------------------------------------------------------------
    # DAT-03: Customers signed up between June 1, 2024 and August 31, 2024
    # -------------------------------------------------------------------------
    summer_signups = sum(
        1 for c in customers if date(2024, 6, 1) <= c["signup_date"] <= date(2024, 8, 31)
    )
    results["DAT-03"] = {
        "columns": ["customer_count"],
        "rows": [[summer_signups]],
    }

    # -------------------------------------------------------------------------
    # DAT-04: Monthly order counts for year 2024
    # -------------------------------------------------------------------------
    month_counts = Counter(
        date(o["order_date"].year, o["order_date"].month, 1)
        for o in orders
        if date(2024, 1, 1) <= o["order_date"] < date(2025, 1, 1)
    )
    sorted_dat_04 = sorted(month_counts.items(), key=lambda x: x[0])
    results["DAT-04"] = {
        "columns": ["order_month", "order_count"],
        "rows": [[m.isoformat() + "T00:00:00+00:00", cnt] for m, cnt in sorted_dat_04],
    }

    # -------------------------------------------------------------------------
    # DAT-05: Compare revenue October 2024 vs September 2024
    # -------------------------------------------------------------------------
    sep_orders = {
        o["id"]
        for o in orders
        if o["status"] != "cancelled" and date(2024, 9, 1) <= o["order_date"] < date(2024, 10, 1)
    }
    sep_rev = sum(
        Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
        for item in order_items
        if item["order_id"] in sep_orders
    )
    results["DAT-05"] = {
        "columns": ["order_month", "monthly_revenue"],
        "rows": [
            ["2024-09-01T00:00:00+00:00", float(round(sep_rev, 2))],
            ["2024-10-01T00:00:00+00:00", float(round(oct_rev, 2))],
        ],
    }

    # -------------------------------------------------------------------------
    # FUL-01: Undelivered orders (placed or shipped)
    # -------------------------------------------------------------------------
    undelivered = sum(1 for o in orders if o["status"] in ("placed", "shipped"))
    results["FUL-01"] = {
        "columns": ["undelivered_count"],
        "rows": [[undelivered]],
    }

    # -------------------------------------------------------------------------
    # FLT-01: Customers in EMEA (empty)
    # -------------------------------------------------------------------------
    results["FLT-01"] = {
        "columns": ["id", "name", "email"],
        "rows": [],
    }

    # -------------------------------------------------------------------------
    # FLT-02: Products priced over $100
    # -------------------------------------------------------------------------
    over_100 = [p for p in products if Decimal(str(p["unit_price"])) > Decimal("100")]
    sorted_flt_02 = sorted(
        over_100, key=lambda p: (-Decimal(str(p["unit_price"])), p["id"])
    )
    results["FLT-02"] = {
        "columns": ["id", "name", "category", "unit_price"],
        "rows": [
            [p["id"], p["name"], p["category"], float(p["unit_price"])]
            for p in sorted_flt_02
        ],
    }

    # -------------------------------------------------------------------------
    # FLT-03: Cancelled orders count
    # -------------------------------------------------------------------------
    cancelled_cnt = sum(1 for o in orders if o["status"] == "cancelled")
    results["FLT-03"] = {
        "columns": ["cancelled_order_count"],
        "rows": [[cancelled_cnt]],
    }

    # -------------------------------------------------------------------------
    # FLT-04: Orders placed on November 1, 2024
    # -------------------------------------------------------------------------
    nov_orders = [o for o in orders if o["order_date"] == date(2024, 11, 1)]
    sorted_flt_04 = sorted(nov_orders, key=lambda o: o["id"])
    results["FLT-04"] = {
        "columns": ["id", "customer_id", "status"],
        "rows": [[o["id"], o["customer_id"], o["status"]] for o in sorted_flt_04],
    }

    # -------------------------------------------------------------------------
    # JOIN-01: Order ID, customer name, order date for placed orders (top 50)
    # -------------------------------------------------------------------------
    placed_orders = [o for o in orders if o["status"] == "placed"]
    sorted_join_01 = sorted(
        placed_orders, key=lambda o: (o["order_date"], o["id"]), reverse=True
    )[:50]
    results["JOIN-01"] = {
        "columns": ["id", "name", "order_date"],
        "rows": [
            [o["id"], cust_map[o["customer_id"]]["name"], o["order_date"].isoformat()]
            for o in sorted_join_01
        ],
    }

    # -------------------------------------------------------------------------
    # JOIN-02: Product name alongside total units sold
    # -------------------------------------------------------------------------
    units_sold: dict[int, int] = defaultdict(int)
    for item in order_items:
        if item["order_id"] in non_cancelled_order_ids:
            units_sold[item["product_id"]] += item["quantity"]
    prod_sold_list = [
        (p["name"], units_sold.get(p["id"], 0)) for p in products
    ]
    sorted_join_02 = sorted(prod_sold_list, key=lambda x: (-x[1], x[0]))
    results["JOIN-02"] = {
        "columns": ["name", "total_units_sold"],
        "rows": [[name, qty] for name, qty in sorted_join_02],
    }

    # -------------------------------------------------------------------------
    # JOIN-03: Customers who have never placed any orders
    # -------------------------------------------------------------------------
    ordered_cids = {o["customer_id"] for o in orders}
    zero_orders = [c for c in customers if c["id"] not in ordered_cids]
    sorted_join_03 = sorted(zero_orders, key=lambda c: c["id"])
    results["JOIN-03"] = {
        "columns": ["id", "name", "email"],
        "rows": [[c["id"], c["name"], c["email"]] for c in sorted_join_03],
    }

    # -------------------------------------------------------------------------
    # PAY-01: Payment methods breakdown by total collected amount
    # -------------------------------------------------------------------------
    completed_payments = [p for p in payments if p["status"] == "completed"]
    pay_methods: dict[str, list[Any]] = defaultdict(lambda: [Decimal("0"), 0])
    for p in completed_payments:
        pay_methods[p["method"]][0] += Decimal(str(p["amount"]))
        pay_methods[p["method"]][1] += 1
    sorted_pay_01 = sorted(pay_methods.items(), key=lambda x: (-x[1][0], x[0]))
    results["PAY-01"] = {
        "columns": ["method", "total_amount", "transaction_count"],
        "rows": [[m, float(round(s[0], 2)), s[1]] for m, s in sorted_pay_01],
    }

    # -------------------------------------------------------------------------
    # PAY-02: Failed or refunded payments count
    # -------------------------------------------------------------------------
    failed_refunded = Counter(
        p["status"] for p in payments if p["status"] in ("failed", "refunded")
    )
    sorted_pay_02 = sorted(failed_refunded.items(), key=lambda x: (-x[1], x[0]))
    results["PAY-02"] = {
        "columns": ["status", "payment_count"],
        "rows": [[s, cnt] for s, cnt in sorted_pay_02],
    }

    return results
