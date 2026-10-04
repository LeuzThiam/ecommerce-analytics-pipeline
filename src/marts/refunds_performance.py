from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_refunds_performance(engine: Engine) -> int:
    """Construit une synthèse spécialisée des remboursements par produit.

    Les ventes définissent l'exposition de chaque produit. Les remboursements
    sont agrégés séparément avec leur date effective afin de mesurer à la fois
    leur fréquence en unités et leur poids financier.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.refunds_performance (
                    product_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_product(product_key),
                    product_id INTEGER NOT NULL UNIQUE,
                    product_name VARCHAR(255) NOT NULL,
                    orders INTEGER NOT NULL,
                    items_sold INTEGER NOT NULL,
                    items_refunded INTEGER NOT NULL,
                    first_refund_date DATE,
                    last_refund_date DATE,
                    gross_revenue_usd NUMERIC(14, 2) NOT NULL,
                    refund_amount_usd NUMERIC(14, 2) NOT NULL,
                    net_revenue_usd NUMERIC(14, 2) NOT NULL,
                    average_refund_amount_usd NUMERIC(14, 2) NOT NULL,
                    refund_rate NUMERIC(8, 4) NOT NULL,
                    refund_value_rate NUMERIC(8, 4) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH sales_by_product AS (
                    SELECT
                        product_key,
                        COUNT(DISTINCT order_id)::integer AS orders,
                        COUNT(*)::integer AS items_sold,
                        SUM(price_usd)::numeric(14, 2) AS gross_revenue_usd
                    FROM warehouse.fact_sales
                    GROUP BY product_key
                ),
                refunds_by_product AS (
                    SELECT
                        v.product_key,
                        COUNT(*)::integer AS items_refunded,
                        MIN(d.date) AS first_refund_date,
                        MAX(d.date) AS last_refund_date,
                        SUM(v.refund_amount_usd)::numeric(14, 2) AS refund_amount_usd
                    FROM warehouse.fact_sales AS v
                    JOIN warehouse.dim_date AS d
                        ON d.date_key = v.refund_date_key
                    WHERE v.is_refunded
                    GROUP BY v.product_key
                ),
                refund_values AS (
                    SELECT
                        p.product_key,
                        p.product_id,
                        p.product_name,
                        COALESCE(s.orders, 0) AS orders,
                        COALESCE(s.items_sold, 0) AS items_sold,
                        COALESCE(r.items_refunded, 0) AS items_refunded,
                        r.first_refund_date,
                        r.last_refund_date,
                        COALESCE(s.gross_revenue_usd, 0) AS gross_revenue_usd,
                        COALESCE(r.refund_amount_usd, 0) AS refund_amount_usd
                    FROM warehouse.dim_product AS p
                    LEFT JOIN sales_by_product AS s USING (product_key)
                    LEFT JOIN refunds_by_product AS r USING (product_key)
                )
                INSERT INTO marts.refunds_performance (
                    product_key,
                    product_id,
                    product_name,
                    orders,
                    items_sold,
                    items_refunded,
                    first_refund_date,
                    last_refund_date,
                    gross_revenue_usd,
                    refund_amount_usd,
                    net_revenue_usd,
                    average_refund_amount_usd,
                    refund_rate,
                    refund_value_rate
                )
                SELECT
                    product_key,
                    product_id,
                    product_name,
                    orders,
                    items_sold,
                    items_refunded,
                    first_refund_date,
                    last_refund_date,
                    gross_revenue_usd,
                    refund_amount_usd,
                    gross_revenue_usd - refund_amount_usd,
                    COALESCE(
                        ROUND(refund_amount_usd / NULLIF(items_refunded, 0), 2),
                        0
                    ),
                    COALESCE(
                        ROUND(items_refunded::numeric / NULLIF(items_sold, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(refund_amount_usd / NULLIF(gross_revenue_usd, 0), 4),
                        0
                    )
                FROM refund_values
                ON CONFLICT (product_key)
                DO UPDATE SET
                    product_id = EXCLUDED.product_id,
                    product_name = EXCLUDED.product_name,
                    orders = EXCLUDED.orders,
                    items_sold = EXCLUDED.items_sold,
                    items_refunded = EXCLUDED.items_refunded,
                    first_refund_date = EXCLUDED.first_refund_date,
                    last_refund_date = EXCLUDED.last_refund_date,
                    gross_revenue_usd = EXCLUDED.gross_revenue_usd,
                    refund_amount_usd = EXCLUDED.refund_amount_usd,
                    net_revenue_usd = EXCLUDED.net_revenue_usd,
                    average_refund_amount_usd = EXCLUDED.average_refund_amount_usd,
                    refund_rate = EXCLUDED.refund_rate,
                    refund_value_rate = EXCLUDED.refund_value_rate
                """
            )
        )
    return result.rowcount
