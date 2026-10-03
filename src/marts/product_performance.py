from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_product_performance(engine: Engine) -> int:
    """Construit une synthèse commerciale par produit du catalogue.

    La dimension produit pilote le chargement afin de conserver également un
    produit sans vente. Les indicateurs financiers proviennent exclusivement
    de ``fact_sales``, déjà réconciliée avec le staging.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.product_performance (
                    product_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_product(product_key),
                    product_id INTEGER NOT NULL UNIQUE,
                    product_name VARCHAR(255) NOT NULL,
                    product_created_at TIMESTAMP NOT NULL,
                    orders INTEGER NOT NULL,
                    units_sold INTEGER NOT NULL,
                    primary_items INTEGER NOT NULL,
                    secondary_items INTEGER NOT NULL,
                    refunded_items INTEGER NOT NULL,
                    gross_revenue_usd NUMERIC(14, 2) NOT NULL,
                    cogs_usd NUMERIC(14, 2) NOT NULL,
                    gross_profit_usd NUMERIC(14, 2) NOT NULL,
                    refund_amount_usd NUMERIC(14, 2) NOT NULL,
                    net_revenue_usd NUMERIC(14, 2) NOT NULL,
                    net_profit_usd NUMERIC(14, 2) NOT NULL,
                    average_selling_price_usd NUMERIC(14, 2) NOT NULL,
                    gross_margin_rate NUMERIC(8, 4) NOT NULL,
                    refund_rate NUMERIC(8, 4) NOT NULL,
                    secondary_item_rate NUMERIC(8, 4) NOT NULL
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
                        COUNT(*)::integer AS units_sold,
                        COUNT(*) FILTER (
                            WHERE is_primary_item
                        )::integer AS primary_items,
                        COUNT(*) FILTER (
                            WHERE NOT is_primary_item
                        )::integer AS secondary_items,
                        COUNT(*) FILTER (
                            WHERE is_refunded
                        )::integer AS refunded_items,
                        SUM(price_usd)::numeric(14, 2) AS gross_revenue_usd,
                        SUM(cogs_usd)::numeric(14, 2) AS cogs_usd,
                        SUM(gross_profit_usd)::numeric(14, 2) AS gross_profit_usd,
                        SUM(refund_amount_usd)::numeric(14, 2) AS refund_amount_usd
                    FROM warehouse.fact_sales
                    GROUP BY product_key
                ),
                product_values AS (
                    SELECT
                        p.product_key,
                        p.product_id,
                        p.product_name,
                        p.created_at AS product_created_at,
                        COALESCE(s.orders, 0) AS orders,
                        COALESCE(s.units_sold, 0) AS units_sold,
                        COALESCE(s.primary_items, 0) AS primary_items,
                        COALESCE(s.secondary_items, 0) AS secondary_items,
                        COALESCE(s.refunded_items, 0) AS refunded_items,
                        COALESCE(s.gross_revenue_usd, 0) AS gross_revenue_usd,
                        COALESCE(s.cogs_usd, 0) AS cogs_usd,
                        COALESCE(s.gross_profit_usd, 0) AS gross_profit_usd,
                        COALESCE(s.refund_amount_usd, 0) AS refund_amount_usd
                    FROM warehouse.dim_product AS p
                    LEFT JOIN sales_by_product AS s USING (product_key)
                )
                INSERT INTO marts.product_performance (
                    product_key,
                    product_id,
                    product_name,
                    product_created_at,
                    orders,
                    units_sold,
                    primary_items,
                    secondary_items,
                    refunded_items,
                    gross_revenue_usd,
                    cogs_usd,
                    gross_profit_usd,
                    refund_amount_usd,
                    net_revenue_usd,
                    net_profit_usd,
                    average_selling_price_usd,
                    gross_margin_rate,
                    refund_rate,
                    secondary_item_rate
                )
                SELECT
                    product_key,
                    product_id,
                    product_name,
                    product_created_at,
                    orders,
                    units_sold,
                    primary_items,
                    secondary_items,
                    refunded_items,
                    gross_revenue_usd,
                    cogs_usd,
                    gross_profit_usd,
                    refund_amount_usd,
                    gross_revenue_usd - refund_amount_usd,
                    gross_profit_usd - refund_amount_usd,
                    COALESCE(
                        ROUND(gross_revenue_usd / NULLIF(units_sold, 0), 2),
                        0
                    ),
                    COALESCE(
                        ROUND(gross_profit_usd / NULLIF(gross_revenue_usd, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(refunded_items::numeric / NULLIF(units_sold, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(secondary_items::numeric / NULLIF(units_sold, 0), 4),
                        0
                    )
                FROM product_values
                ON CONFLICT (product_key)
                DO UPDATE SET
                    product_id = EXCLUDED.product_id,
                    product_name = EXCLUDED.product_name,
                    product_created_at = EXCLUDED.product_created_at,
                    orders = EXCLUDED.orders,
                    units_sold = EXCLUDED.units_sold,
                    primary_items = EXCLUDED.primary_items,
                    secondary_items = EXCLUDED.secondary_items,
                    refunded_items = EXCLUDED.refunded_items,
                    gross_revenue_usd = EXCLUDED.gross_revenue_usd,
                    cogs_usd = EXCLUDED.cogs_usd,
                    gross_profit_usd = EXCLUDED.gross_profit_usd,
                    refund_amount_usd = EXCLUDED.refund_amount_usd,
                    net_revenue_usd = EXCLUDED.net_revenue_usd,
                    net_profit_usd = EXCLUDED.net_profit_usd,
                    average_selling_price_usd = EXCLUDED.average_selling_price_usd,
                    gross_margin_rate = EXCLUDED.gross_margin_rate,
                    refund_rate = EXCLUDED.refund_rate,
                    secondary_item_rate = EXCLUDED.secondary_item_rate
                """
            )
        )
    return result.rowcount
