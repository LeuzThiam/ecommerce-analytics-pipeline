from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_fact_sales(engine: Engine) -> int:
    """Construit une ligne de faits par article commandé.

    Les remboursements sont d'abord agrégés par article. Le grain reste ainsi
    stable même si la source accepte un jour plusieurs remboursements pour un
    même ``order_item_id``.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.fact_sales (
                    sales_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    order_item_id BIGINT NOT NULL UNIQUE,
                    order_id BIGINT NOT NULL,
                    website_session_id BIGINT NOT NULL,
                    date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
                    refund_date_key INTEGER REFERENCES warehouse.dim_date(date_key),
                    product_key INTEGER NOT NULL REFERENCES warehouse.dim_product(product_key),
                    customer_key INTEGER NOT NULL REFERENCES warehouse.dim_customer(customer_key),
                    is_primary_item BOOLEAN NOT NULL,
                    is_refunded BOOLEAN NOT NULL,
                    price_usd NUMERIC(12, 2) NOT NULL,
                    cogs_usd NUMERIC(12, 2) NOT NULL,
                    gross_profit_usd NUMERIC(12, 2) NOT NULL,
                    refund_amount_usd NUMERIC(12, 2) NOT NULL,
                    net_revenue_usd NUMERIC(12, 2) NOT NULL,
                    net_profit_usd NUMERIC(12, 2) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH refunds_by_item AS (
                    SELECT
                        order_item_id,
                        SUM(refund_amount_usd)::numeric(12, 2) AS refund_amount_usd,
                        MAX(created_at) AS last_refund_at
                    FROM staging.order_item_refunds
                    GROUP BY order_item_id
                )
                INSERT INTO warehouse.fact_sales (
                    order_item_id,
                    order_id,
                    website_session_id,
                    date_key,
                    refund_date_key,
                    product_key,
                    customer_key,
                    is_primary_item,
                    is_refunded,
                    price_usd,
                    cogs_usd,
                    gross_profit_usd,
                    refund_amount_usd,
                    net_revenue_usd,
                    net_profit_usd
                )
                SELECT
                    i.order_item_id,
                    i.order_id,
                    o.website_session_id,
                    TO_CHAR(i.created_at, 'YYYYMMDD')::integer,
                    CASE
                        WHEN r.last_refund_at IS NOT NULL
                        THEN TO_CHAR(r.last_refund_at, 'YYYYMMDD')::integer
                    END,
                    p.product_key,
                    c.customer_key,
                    i.is_primary_item = 1,
                    r.order_item_id IS NOT NULL,
                    i.price_usd::numeric(12, 2),
                    i.cogs_usd::numeric(12, 2),
                    i.gross_profit::numeric(12, 2),
                    COALESCE(r.refund_amount_usd, 0)::numeric(12, 2),
                    (i.price_usd - COALESCE(r.refund_amount_usd, 0))::numeric(12, 2),
                    (i.gross_profit - COALESCE(r.refund_amount_usd, 0))::numeric(12, 2)
                FROM staging.order_items AS i
                JOIN staging.orders AS o USING (order_id)
                JOIN warehouse.dim_product AS p USING (product_id)
                JOIN warehouse.dim_customer AS c USING (user_id)
                LEFT JOIN refunds_by_item AS r USING (order_item_id)
                ON CONFLICT (order_item_id)
                DO UPDATE SET
                    order_id = EXCLUDED.order_id,
                    website_session_id = EXCLUDED.website_session_id,
                    date_key = EXCLUDED.date_key,
                    refund_date_key = EXCLUDED.refund_date_key,
                    product_key = EXCLUDED.product_key,
                    customer_key = EXCLUDED.customer_key,
                    is_primary_item = EXCLUDED.is_primary_item,
                    is_refunded = EXCLUDED.is_refunded,
                    price_usd = EXCLUDED.price_usd,
                    cogs_usd = EXCLUDED.cogs_usd,
                    gross_profit_usd = EXCLUDED.gross_profit_usd,
                    refund_amount_usd = EXCLUDED.refund_amount_usd,
                    net_revenue_usd = EXCLUDED.net_revenue_usd,
                    net_profit_usd = EXCLUDED.net_profit_usd
                """
            )
        )
    return result.rowcount
