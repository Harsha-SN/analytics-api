from flask import Flask, jsonify
from flask_cors import CORS

from product_performance import (
    get_engine,
    load_data,
    prepare_data,
    top_selling_products,
    product_return_analysis,
    category_performance,
)

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

# Allow requests from Superset / browser
CORS(app)


# ============================================================
# LOAD ANALYTICS DATA
# ============================================================

def get_sales_data():

    engine = get_engine()

    try:

        # Load star-schema data
        sales, products = load_data(engine)

        # Prepare / join data
        sales = prepare_data(
            sales,
            products
        )

        return sales, products

    finally:

        engine.dispose()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "success",
        "message": "Product Performance Analytics API is running"
    })


# ============================================================
# REVENUE BY CATEGORY
# ============================================================

@app.route(
    "/api/product-performance/categories",
    methods=["GET"]
)
def categories():

    try:

        sales, products = get_sales_data()

        # Run analytics
        result = category_performance(sales)

        # Convert DataFrame → JSON
        data = result[
            [
                "category",
                "orders",
                "quantity_sold",
                "revenue",
                "return_rate"
            ]
        ].copy()

        # Replace NaN / Infinity values
        data = data.fillna(0)

        return jsonify(
            data.to_dict(orient="records")
        )

    except Exception as e:

        print("[API ERROR - CATEGORIES]", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# TOP 10 SELLING PRODUCTS
# ============================================================

@app.route(
    "/api/product-performance/top-selling-products",
    methods=["GET"]
)
def top_selling():

    try:

        sales, products = get_sales_data()

        # Run analytics
        result = top_selling_products(sales)

        # The analytics function returns the complete
        # product_sales DataFrame, already sorted.
        data = result.head(10).copy()

        data = data[
            [
                "product_name",
                "category",
                "quantity_sold",
                "orders",
                "revenue",
                "revenue_share"
            ]
        ]

        # Replace NaN values
        data = data.fillna(0)

        return jsonify(
            data.to_dict(orient="records")
        )

    except Exception as e:

        print("[API ERROR - TOP SELLING]", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# PRODUCT RETURN ANALYSIS
# ============================================================

@app.route(
    "/api/product-performance/returns",
    methods=["GET"]
)
def returns():

    try:

        sales, products = get_sales_data()

        result = product_return_analysis(sales)

        data = result.head(10).copy()

        data = data[
            [
                "product_name",
                "category",
                "total_orders",
                "returned_orders",
                "return_rate"
            ]
        ]

        data = data.fillna(0)

        return jsonify(
            data.to_dict(orient="records")
        )

    except Exception as e:

        print("[API ERROR - RETURNS]", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("PRODUCT PERFORMANCE ANALYTICS API")
    print("=" * 60)

    print(
        "API running at: "
        "http://127.0.0.1:5000"
    )

    print(
        "Categories:"
        " http://127.0.0.1:5000/"
        "api/product-performance/categories"
    )

    print(
        "Top products:"
        " http://127.0.0.1:5000/"
        "api/product-performance/top-selling-products"
    )

    print(
        "Returns:"
        " http://127.0.0.1:5000/"
        "api/product-performance/returns"
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )