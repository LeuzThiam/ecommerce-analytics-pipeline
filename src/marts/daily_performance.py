from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_daily_performance(engine: Engine) -> int:
    """Construit une ligne de performance par date calendaire.

    Les sessions, les ventes et les remboursements sont agrégés séparément
    avant leurs jointures. Un remboursement est attribué à sa date effective,
    et non à la date de la vente d'origine.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.daily_performance (
                    date_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_date(date_key),
                    date DATE NOT NULL UNIQUE,
                    sessions INTEGER NOT NULL,
                    unique_visitors INTEGER NOT NULL,
                    repeat_sessions INTEGER NOT NULL,
                    pageviews BIGINT NOT NULL,
                    bounces INTEGER NOT NULL,
                    converted_sessions INTEGER NOT NULL,
                    orders INTEGER NOT NULL,
                    items_purchased INTEGER NOT NULL,
                    gross_revenue_usd NUMERIC(14, 2) NOT NULL,
                    gross_profit_usd NUMERIC(14, 2) NOT NULL,
                    refund_amount_usd NUMERIC(14, 2) NOT NULL,
                    net_revenue_usd NUMERIC(14, 2) NOT NULL,
                    net_profit_usd NUMERIC(14, 2) NOT NULL,
                    conversion_rate NUMERIC(8, 4) NOT NULL,
                    bounce_rate NUMERIC(8, 4) NOT NULL,
                    average_order_value_usd NUMERIC(14, 2) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH sessions_by_date AS (
                    SELECT
                        date_key,
                        COUNT(*)::integer AS sessions,
                        COUNT(DISTINCT customer_key)::integer AS unique_visitors,
                        COUNT(*) FILTER (
                            WHERE is_repeat_session
                        )::integer AS repeat_sessions,
                        SUM(pageview_count)::bigint AS pageviews,
                        COUNT(*) FILTER (WHERE is_bounce)::integer AS bounces,
                        COUNT(*) FILTER (
                            WHERE is_converted
                        )::integer AS converted_sessions
                    FROM warehouse.fact_sessions
                    GROUP BY date_key
                ),
                sales_by_date AS (
                    SELECT
                        date_key,
                        COUNT(DISTINCT order_id)::integer AS orders,
                        COUNT(*)::integer AS items_purchased,
                        SUM(price_usd)::numeric(14, 2) AS gross_revenue_usd,
                        SUM(gross_profit_usd)::numeric(14, 2) AS gross_profit_usd
                    FROM warehouse.fact_sales
                    GROUP BY date_key
                ),
                refunds_by_date AS (
                    SELECT
                        refund_date_key AS date_key,
                        SUM(refund_amount_usd)::numeric(14, 2) AS refund_amount_usd
                    FROM warehouse.fact_sales
                    WHERE refund_date_key IS NOT NULL
                    GROUP BY refund_date_key
                ),
                daily_values AS (
                    SELECT
                        d.date_key,
                        d.date,
                        COALESCE(s.sessions, 0) AS sessions,
                        COALESCE(s.unique_visitors, 0) AS unique_visitors,
                        COALESCE(s.repeat_sessions, 0) AS repeat_sessions,
                        COALESCE(s.pageviews, 0) AS pageviews,
                        COALESCE(s.bounces, 0) AS bounces,
                        COALESCE(s.converted_sessions, 0) AS converted_sessions,
                        COALESCE(v.orders, 0) AS orders,
                        COALESCE(v.items_purchased, 0) AS items_purchased,
                        COALESCE(v.gross_revenue_usd, 0) AS gross_revenue_usd,
                        COALESCE(v.gross_profit_usd, 0) AS gross_profit_usd,
                        COALESCE(r.refund_amount_usd, 0) AS refund_amount_usd
                    FROM warehouse.dim_date AS d
                    LEFT JOIN sessions_by_date AS s USING (date_key)
                    LEFT JOIN sales_by_date AS v USING (date_key)
                    LEFT JOIN refunds_by_date AS r USING (date_key)
                )
                INSERT INTO marts.daily_performance (
                    date_key,
                    date,
                    sessions,
                    unique_visitors,
                    repeat_sessions,
                    pageviews,
                    bounces,
                    converted_sessions,
                    orders,
                    items_purchased,
                    gross_revenue_usd,
                    gross_profit_usd,
                    refund_amount_usd,
                    net_revenue_usd,
                    net_profit_usd,
                    conversion_rate,
                    bounce_rate,
                    average_order_value_usd
                )
                SELECT
                    date_key,
                    date,
                    sessions,
                    unique_visitors,
                    repeat_sessions,
                    pageviews,
                    bounces,
                    converted_sessions,
                    orders,
                    items_purchased,
                    gross_revenue_usd,
                    gross_profit_usd,
                    refund_amount_usd,
                    gross_revenue_usd - refund_amount_usd,
                    gross_profit_usd - refund_amount_usd,
                    COALESCE(
                        ROUND(converted_sessions::numeric / NULLIF(sessions, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(bounces::numeric / NULLIF(sessions, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(gross_revenue_usd / NULLIF(orders, 0), 2),
                        0
                    )
                FROM daily_values
                ON CONFLICT (date_key)
                DO UPDATE SET
                    date = EXCLUDED.date,
                    sessions = EXCLUDED.sessions,
                    unique_visitors = EXCLUDED.unique_visitors,
                    repeat_sessions = EXCLUDED.repeat_sessions,
                    pageviews = EXCLUDED.pageviews,
                    bounces = EXCLUDED.bounces,
                    converted_sessions = EXCLUDED.converted_sessions,
                    orders = EXCLUDED.orders,
                    items_purchased = EXCLUDED.items_purchased,
                    gross_revenue_usd = EXCLUDED.gross_revenue_usd,
                    gross_profit_usd = EXCLUDED.gross_profit_usd,
                    refund_amount_usd = EXCLUDED.refund_amount_usd,
                    net_revenue_usd = EXCLUDED.net_revenue_usd,
                    net_profit_usd = EXCLUDED.net_profit_usd,
                    conversion_rate = EXCLUDED.conversion_rate,
                    bounce_rate = EXCLUDED.bounce_rate,
                    average_order_value_usd = EXCLUDED.average_order_value_usd
                """
            )
        )
    return result.rowcount
