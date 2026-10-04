from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_customer_summary(engine: Engine) -> int:
    """Construit une synthèse comportementale et commerciale par client.

    ``dim_customer`` pilote la jointure pour conserver les prospects sans
    achat. Les sessions et les ventes sont agrégées séparément afin de ne pas
    multiplier les montants par le nombre de visites.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.customer_summary (
                    customer_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_customer(customer_key),
                    user_id BIGINT NOT NULL UNIQUE,
                    first_session_at TIMESTAMP,
                    last_session_at TIMESTAMP,
                    first_order_at TIMESTAMP,
                    last_order_date DATE,
                    customer_status VARCHAR(30) NOT NULL,
                    session_count INTEGER NOT NULL,
                    repeat_session_count INTEGER NOT NULL,
                    order_count INTEGER NOT NULL,
                    items_purchased INTEGER NOT NULL,
                    gross_revenue_usd NUMERIC(14, 2) NOT NULL,
                    refund_amount_usd NUMERIC(14, 2) NOT NULL,
                    lifetime_revenue_usd NUMERIC(14, 2) NOT NULL,
                    lifetime_profit_usd NUMERIC(14, 2) NOT NULL,
                    average_order_value_usd NUMERIC(14, 2) NOT NULL,
                    days_to_first_order INTEGER,
                    is_repeat_buyer BOOLEAN NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH sessions_by_customer AS (
                    SELECT
                        customer_key,
                        COUNT(*)::integer AS session_count,
                        COUNT(*) FILTER (
                            WHERE is_repeat_session
                        )::integer AS repeat_session_count
                    FROM warehouse.fact_sessions
                    GROUP BY customer_key
                ),
                sales_by_customer AS (
                    SELECT
                        v.customer_key,
                        COUNT(DISTINCT v.order_id)::integer AS order_count,
                        COUNT(*)::integer AS items_purchased,
                        MAX(d.date) AS last_order_date,
                        SUM(v.price_usd)::numeric(14, 2) AS gross_revenue_usd,
                        SUM(v.refund_amount_usd)::numeric(14, 2) AS refund_amount_usd,
                        SUM(v.net_revenue_usd)::numeric(14, 2) AS lifetime_revenue_usd,
                        SUM(v.net_profit_usd)::numeric(14, 2) AS lifetime_profit_usd
                    FROM warehouse.fact_sales AS v
                    JOIN warehouse.dim_date AS d USING (date_key)
                    GROUP BY v.customer_key
                ),
                customer_values AS (
                    SELECT
                        c.customer_key,
                        c.user_id,
                        c.first_session_at,
                        c.last_session_at,
                        c.first_order_at,
                        v.last_order_date,
                        COALESCE(s.session_count, 0) AS session_count,
                        COALESCE(s.repeat_session_count, 0) AS repeat_session_count,
                        COALESCE(v.order_count, 0) AS order_count,
                        COALESCE(v.items_purchased, 0) AS items_purchased,
                        COALESCE(v.gross_revenue_usd, 0) AS gross_revenue_usd,
                        COALESCE(v.refund_amount_usd, 0) AS refund_amount_usd,
                        COALESCE(v.lifetime_revenue_usd, 0) AS lifetime_revenue_usd,
                        COALESCE(v.lifetime_profit_usd, 0) AS lifetime_profit_usd
                    FROM warehouse.dim_customer AS c
                    LEFT JOIN sessions_by_customer AS s USING (customer_key)
                    LEFT JOIN sales_by_customer AS v USING (customer_key)
                )
                INSERT INTO marts.customer_summary (
                    customer_key,
                    user_id,
                    first_session_at,
                    last_session_at,
                    first_order_at,
                    last_order_date,
                    customer_status,
                    session_count,
                    repeat_session_count,
                    order_count,
                    items_purchased,
                    gross_revenue_usd,
                    refund_amount_usd,
                    lifetime_revenue_usd,
                    lifetime_profit_usd,
                    average_order_value_usd,
                    days_to_first_order,
                    is_repeat_buyer
                )
                SELECT
                    customer_key,
                    user_id,
                    first_session_at,
                    last_session_at,
                    first_order_at,
                    last_order_date,
                    CASE
                        WHEN order_count = 0 THEN 'prospect'
                        WHEN order_count = 1 THEN 'acheteur'
                        ELSE 'acheteur récurrent'
                    END,
                    session_count,
                    repeat_session_count,
                    order_count,
                    items_purchased,
                    gross_revenue_usd,
                    refund_amount_usd,
                    lifetime_revenue_usd,
                    lifetime_profit_usd,
                    COALESCE(
                        ROUND(gross_revenue_usd / NULLIF(order_count, 0), 2),
                        0
                    ),
                    CASE
                        WHEN first_order_at IS NOT NULL
                            AND first_session_at IS NOT NULL
                        THEN first_order_at::date - first_session_at::date
                    END,
                    order_count > 1
                FROM customer_values
                ON CONFLICT (customer_key)
                DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    first_session_at = EXCLUDED.first_session_at,
                    last_session_at = EXCLUDED.last_session_at,
                    first_order_at = EXCLUDED.first_order_at,
                    last_order_date = EXCLUDED.last_order_date,
                    customer_status = EXCLUDED.customer_status,
                    session_count = EXCLUDED.session_count,
                    repeat_session_count = EXCLUDED.repeat_session_count,
                    order_count = EXCLUDED.order_count,
                    items_purchased = EXCLUDED.items_purchased,
                    gross_revenue_usd = EXCLUDED.gross_revenue_usd,
                    refund_amount_usd = EXCLUDED.refund_amount_usd,
                    lifetime_revenue_usd = EXCLUDED.lifetime_revenue_usd,
                    lifetime_profit_usd = EXCLUDED.lifetime_profit_usd,
                    average_order_value_usd = EXCLUDED.average_order_value_usd,
                    days_to_first_order = EXCLUDED.days_to_first_order,
                    is_repeat_buyer = EXCLUDED.is_repeat_buyer
                """
            )
        )
    return result.rowcount
