from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_marketing_performance(engine: Engine) -> int:
    """Construit une synthèse de performance par combinaison marketing.

    Les ventes sont reliées au canal de la session d'origine grâce à
    ``website_session_id``. Les agrégats de navigation et de vente restent
    séparés jusqu'à la jointure finale pour préserver leurs grains respectifs.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.marketing_performance (
                    marketing_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_marketing(marketing_key),
                    utm_source VARCHAR(100) NOT NULL,
                    utm_campaign VARCHAR(100) NOT NULL,
                    utm_content VARCHAR(255) NOT NULL,
                    http_referer VARCHAR(500) NOT NULL,
                    is_direct BOOLEAN NOT NULL,
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
                    average_order_value_usd NUMERIC(14, 2) NOT NULL,
                    revenue_per_session_usd NUMERIC(14, 2) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH sessions_by_marketing AS (
                    SELECT
                        marketing_key,
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
                    GROUP BY marketing_key
                ),
                sales_by_marketing AS (
                    SELECT
                        s.marketing_key,
                        COUNT(DISTINCT v.order_id)::integer AS orders,
                        COUNT(*)::integer AS items_purchased,
                        SUM(v.price_usd)::numeric(14, 2) AS gross_revenue_usd,
                        SUM(v.gross_profit_usd)::numeric(14, 2) AS gross_profit_usd,
                        SUM(v.refund_amount_usd)::numeric(14, 2) AS refund_amount_usd
                    FROM warehouse.fact_sales AS v
                    JOIN warehouse.fact_sessions AS s USING (website_session_id)
                    GROUP BY s.marketing_key
                ),
                marketing_values AS (
                    SELECT
                        m.marketing_key,
                        m.utm_source,
                        m.utm_campaign,
                        m.utm_content,
                        m.http_referer,
                        m.is_direct,
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
                        COALESCE(v.refund_amount_usd, 0) AS refund_amount_usd
                    FROM warehouse.dim_marketing AS m
                    LEFT JOIN sessions_by_marketing AS s USING (marketing_key)
                    LEFT JOIN sales_by_marketing AS v USING (marketing_key)
                )
                INSERT INTO marts.marketing_performance (
                    marketing_key,
                    utm_source,
                    utm_campaign,
                    utm_content,
                    http_referer,
                    is_direct,
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
                    average_order_value_usd,
                    revenue_per_session_usd
                )
                SELECT
                    marketing_key,
                    utm_source,
                    utm_campaign,
                    utm_content,
                    http_referer,
                    is_direct,
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
                    ),
                    COALESCE(
                        ROUND(gross_revenue_usd / NULLIF(sessions, 0), 2),
                        0
                    )
                FROM marketing_values
                ON CONFLICT (marketing_key)
                DO UPDATE SET
                    utm_source = EXCLUDED.utm_source,
                    utm_campaign = EXCLUDED.utm_campaign,
                    utm_content = EXCLUDED.utm_content,
                    http_referer = EXCLUDED.http_referer,
                    is_direct = EXCLUDED.is_direct,
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
                    average_order_value_usd = EXCLUDED.average_order_value_usd,
                    revenue_per_session_usd = EXCLUDED.revenue_per_session_usd
                """
            )
        )
    return result.rowcount
