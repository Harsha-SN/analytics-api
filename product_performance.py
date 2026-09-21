import os
import pandas as pd
from sqlalchemy import create_engine, text

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "AnalyticsDB"
DB_USER = "postgres"
DB_PASSWORD = "harsha@10"

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:"
    f"{DB_PASSWORD.replace('@', '%40')}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def get_engine():
    try:
        engine = create_engine(DATABASE_URL)

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("[DB] Connected to AnalyticsDB")

        return engine

    except Exception as e:
        print("[DB ERROR]", e)
        raise
# ============================================================
# LOAD DATA FROM DBT STAR SCHEMA
# ============================================================

def load_data(engine):

    print("[DATA] Reading fact_sales...")

    sales_query = """
        SELECT
            sales_key,
            order_id,
            product_id,
            customer_id,
            date_key,
            quantity,
            unit_price,
            discount,
            gross_amount,
            discount_amount,
            net_amount,
            order_status
        FROM analytics.fact_sales
    """

    sales = pd.read_sql(sales_query, engine)

    print(f"[DATA] Sales rows: {len(sales):,}")

    print("[DATA] Reading dim_products...")

    products_query = """
        SELECT
            product_id,
            product_name,
            category,
            brand,
            unit_price
        FROM analytics.dim_products
    """

    products = pd.read_sql(products_query, engine)

    print(f"[DATA] Products: {len(products):,}")

    return sales, products


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(sales, products):

    # Make sure numeric columns are numeric
    numeric_columns = [
        "quantity",
        "unit_price",
        "gross_amount",
        "discount_amount",
        "net_amount"
    ]

    for column in numeric_columns:
        sales[column] = pd.to_numeric(
            sales[column],
            errors="coerce"
        ).fillna(0)

    # Normalize order status
    sales["order_status"] = (
        sales["order_status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # Join product information
    sales = sales.merge(
        products,
        on="product_id",
        how="left",
        suffixes=("", "_product")
    )

    # Handle missing product names/categories
    sales["product_name"] = sales["product_name"].fillna(
        "Unknown Product"
    )

    sales["category"] = sales["category"].fillna(
        "Unknown Category"
    )

    sales["brand"] = sales["brand"].fillna(
        "Unknown Brand"
    )

    return sales


# ============================================================
# 1. TOP-SELLING PRODUCTS
# ============================================================

def top_selling_products(sales):

    print("\n")
    print("=" * 70)
    print("1. TOP-SELLING PRODUCTS")
    print("=" * 70)

    product_sales = (
        sales
        .groupby(
            ["product_id", "product_name", "category"],
            as_index=False
        )
        .agg(
            quantity_sold=("quantity", "sum"),
            orders=("order_id", "nunique"),
            revenue=("net_amount", "sum")
        )
    )

    # Total revenue
    total_revenue = product_sales["revenue"].sum()

    if total_revenue > 0:
        product_sales["revenue_share"] = (
            product_sales["revenue"]
            / total_revenue
            * 100
        )
    else:
        product_sales["revenue_share"] = 0

    # Rank by quantity sold
    product_sales = product_sales.sort_values(
        ["quantity_sold", "revenue"],
        ascending=[False, False]
    )

    top_products = product_sales.head(10).copy()

    top_products["revenue"] = top_products["revenue"].round(2)
    top_products["revenue_share"] = (
        top_products["revenue_share"].round(2)
    )

    print(
        top_products[
            [
                "product_name",
                "category",
                "quantity_sold",
                "orders",
                "revenue",
                "revenue_share"
            ]
        ].to_string(index=False)
    )

    # Business insight
    if not top_products.empty:

        top = top_products.iloc[0]

        print("\nINSIGHT:")
        print(
            f"{top['product_name']} is the top-selling product "
            f"with {int(top['quantity_sold']):,} units sold "
            f"across {int(top['orders']):,} orders."
        )

    return product_sales


# ============================================================
# 2. PRODUCT RETURN ANALYSIS
# ============================================================

def product_return_analysis(sales):

    print("\n")
    print("=" * 70)
    print("2. PRODUCT RETURN ANALYSIS")
    print("=" * 70)

    # All orders containing the product
    product_orders = (
        sales
        .groupby(
            ["product_id", "product_name", "category"],
            as_index=False
        )
        .agg(
            total_orders=("order_id", "nunique"),
            quantity_sold=("quantity", "sum")
        )
    )

    # Returned orders
    returned_sales = sales[
        sales["order_status"] == "returned"
    ]

    returned_orders = (
        returned_sales
        .groupby(
            ["product_id", "product_name", "category"],
            as_index=False
        )
        .agg(
            returned_orders=("order_id", "nunique"),
            returned_quantity=("quantity", "sum")
        )
    )

    # Combine
    return_analysis = product_orders.merge(
        returned_orders,
        on=["product_id", "product_name", "category"],
        how="left"
    )

    return_analysis["returned_orders"] = (
        return_analysis["returned_orders"]
        .fillna(0)
    )

    return_analysis["returned_quantity"] = (
        return_analysis["returned_quantity"]
        .fillna(0)
    )

    # Return rate
    return_analysis["return_rate"] = (
        return_analysis["returned_orders"]
        / return_analysis["total_orders"]
        * 100
    )

    # Only products with reasonable sales volume
    # This avoids highlighting products with 1 order and 1 return.
    return_analysis = return_analysis[
        return_analysis["total_orders"] >= 10
    ]

    return_analysis = return_analysis.sort_values(
        "return_rate",
        ascending=False
    )

    top_returns = return_analysis.head(10).copy()

    top_returns["return_rate"] = (
        top_returns["return_rate"].round(2)
    )

    print(
        top_returns[
            [
                "product_name",
                "category",
                "total_orders",
                "returned_orders",
                "return_rate"
            ]
        ].to_string(index=False)
    )

    # Business insight
    if not top_returns.empty:

        highest_return = top_returns.iloc[0]

        print("\nINSIGHT:")

        print(
            f"{highest_return['product_name']} has the highest "
            f"return rate at {highest_return['return_rate']:.2f}% "
            f"among products with at least 10 orders."
        )

    return return_analysis


# ============================================================
# 3. CATEGORY PERFORMANCE
# ============================================================

def category_performance(sales):

    print("\n")
    print("=" * 70)
    print("3. CATEGORY PERFORMANCE")
    print("=" * 70)

    category_sales = (
        sales
        .groupby("category", as_index=False)
        .agg(
            quantity_sold=("quantity", "sum"),
            orders=("order_id", "nunique"),
            revenue=("net_amount", "sum")
        )
    )

    # Returned orders by category
    returned_sales = sales[
        sales["order_status"] == "returned"
    ]

    category_returns = (
        returned_sales
        .groupby("category", as_index=False)
        .agg(
            returned_orders=("order_id", "nunique")
        )
    )

    category_sales = category_sales.merge(
        category_returns,
        on="category",
        how="left"
    )

    category_sales["returned_orders"] = (
        category_sales["returned_orders"]
        .fillna(0)
    )

    category_sales["return_rate"] = (
        category_sales["returned_orders"]
        / category_sales["orders"]
        * 100
    )

    category_sales = category_sales.sort_values(
        "revenue",
        ascending=False
    )

    category_sales["revenue"] = (
        category_sales["revenue"].round(2)
    )

    category_sales["return_rate"] = (
        category_sales["return_rate"].round(2)
    )

    print(
        category_sales[
            [
                "category",
                "orders",
                "quantity_sold",
                "revenue",
                "return_rate"
            ]
        ].to_string(index=False)
    )

    # Business insights
    if not category_sales.empty:

        best_category = category_sales.iloc[0]

        worst_return_category = category_sales.sort_values(
            "return_rate",
            ascending=False
        ).iloc[0]

        print("\nINSIGHTS:")

        print(
            f"Highest revenue category: "
            f"{best_category['category']} "
            f"with ₹{best_category['revenue']:,.2f}."
        )

        print(
            f"Highest return-rate category: "
            f"{worst_return_category['category']} "
            f"with {worst_return_category['return_rate']:.2f}%."
        )

    return category_sales


# ============================================================
# OVERALL BUSINESS SUMMARY
# ============================================================

def overall_summary(sales, products):

    print("\n")
    print("=" * 70)
    print("PRODUCT PERFORMANCE & RETURN ANALYSIS")
    print("=" * 70)

    total_products = sales["product_id"].nunique()
    total_orders = sales["order_id"].nunique()
    total_quantity = sales["quantity"].sum()
    total_revenue = sales["net_amount"].sum()

    returned_orders = sales[
        sales["order_status"] == "returned"
    ]["order_id"].nunique()

    overall_return_rate = (
        returned_orders / total_orders * 100
        if total_orders > 0
        else 0
    )

    print(f"Products analyzed       : {total_products:,}")
    print(f"Orders analyzed         : {total_orders:,}")
    print(f"Quantity sold           : {total_quantity:,.0f}")
    print(f"Net revenue             : ₹{total_revenue:,.2f}")
    print(f"Returned orders         : {returned_orders:,}")
    print(f"Overall return rate     : {overall_return_rate:.2f}%")


# ============================================================
# MAIN
# ============================================================

def main():

    print("\nStarting Product Performance Analytics...")

    engine = get_engine()

    try:

        # 1. Read star-schema data
        sales, products = load_data(engine)

        # 2. Prepare/join data
        sales = prepare_data(
            sales,
            products
        )

        # 3. Overall summary
        overall_summary(
            sales,
            products
        )

        # 4. Top-selling products
        top_selling_products(
            sales
        )

        # 5. Return analysis
        product_return_analysis(
            sales
        )

        # 6. Category analysis
        category_performance(
            sales
        )

        print("\n")
        print("=" * 70)
        print("ANALYSIS COMPLETED")
        print("=" * 70)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()