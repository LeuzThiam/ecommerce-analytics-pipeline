from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_fact_sessions(engine: Engine) -> int:
    """Construit une ligne analytique par session web.

    Les pages vues et les commandes sont agrégées séparément avant leurs
    jointures. Cette précaution empêche leur produit cartésien de gonfler les
    métriques lorsqu'une session contient plusieurs pages ou commandes.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.fact_sessions (
                    session_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    website_session_id BIGINT NOT NULL UNIQUE,
                    date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
                    customer_key INTEGER NOT NULL REFERENCES warehouse.dim_customer(customer_key),
                    marketing_key INTEGER NOT NULL REFERENCES warehouse.dim_marketing(marketing_key),
                    device_key INTEGER NOT NULL REFERENCES warehouse.dim_device(device_key),
                    session_started_at TIMESTAMP NOT NULL,
                    landing_page_url TEXT NOT NULL,
                    exit_page_url TEXT NOT NULL,
                    pageview_count INTEGER NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    is_repeat_session BOOLEAN NOT NULL,
                    is_bounce BOOLEAN NOT NULL,
                    is_converted BOOLEAN NOT NULL,
                    order_count INTEGER NOT NULL,
                    items_purchased INTEGER NOT NULL,
                    revenue_usd NUMERIC(12, 2) NOT NULL,
                    gross_profit_usd NUMERIC(12, 2) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH pageviews_by_session AS (
                    SELECT
                        website_session_id,
                        COUNT(*)::integer AS pageview_count,
                        (ARRAY_AGG(
                            pageview_url
                            ORDER BY created_at, website_pageview_id
                        ))[1] AS landing_page_url,
                        (ARRAY_AGG(
                            pageview_url
                            ORDER BY created_at DESC, website_pageview_id DESC
                        ))[1] AS exit_page_url,
                        EXTRACT(
                            EPOCH FROM (MAX(created_at) - MIN(created_at))
                        )::integer AS duration_seconds
                    FROM staging.website_pageviews
                    GROUP BY website_session_id
                ),
                orders_by_session AS (
                    SELECT
                        website_session_id,
                        COUNT(*)::integer AS order_count,
                        SUM(items_purchased)::integer AS items_purchased,
                        SUM(price_usd)::numeric(12, 2) AS revenue_usd,
                        SUM(gross_profit)::numeric(12, 2) AS gross_profit_usd
                    FROM staging.orders
                    GROUP BY website_session_id
                )
                INSERT INTO warehouse.fact_sessions (
                    website_session_id,
                    date_key,
                    customer_key,
                    marketing_key,
                    device_key,
                    session_started_at,
                    landing_page_url,
                    exit_page_url,
                    pageview_count,
                    duration_seconds,
                    is_repeat_session,
                    is_bounce,
                    is_converted,
                    order_count,
                    items_purchased,
                    revenue_usd,
                    gross_profit_usd
                )
                SELECT
                    s.website_session_id,
                    TO_CHAR(s.created_at, 'YYYYMMDD')::integer,
                    c.customer_key,
                    m.marketing_key,
                    d.device_key,
                    s.created_at,
                    p.landing_page_url,
                    p.exit_page_url,
                    p.pageview_count,
                    p.duration_seconds,
                    s.is_repeat_session = 1,
                    p.pageview_count = 1,
                    o.website_session_id IS NOT NULL,
                    COALESCE(o.order_count, 0),
                    COALESCE(o.items_purchased, 0),
                    COALESCE(o.revenue_usd, 0)::numeric(12, 2),
                    COALESCE(o.gross_profit_usd, 0)::numeric(12, 2)
                FROM staging.website_sessions AS s
                JOIN pageviews_by_session AS p USING (website_session_id)
                JOIN warehouse.dim_customer AS c USING (user_id)
                JOIN warehouse.dim_device AS d USING (device_type)
                JOIN warehouse.dim_marketing AS m
                    ON m.utm_source = COALESCE(s.utm_source, '(non renseigné)')
                    AND m.utm_campaign = COALESCE(
                        s.utm_campaign,
                        '(non renseignée)'
                    )
                    AND m.utm_content = COALESCE(
                        s.utm_content,
                        '(non renseigné)'
                    )
                    AND m.http_referer = COALESCE(s.http_referer, '(aucun)')
                LEFT JOIN orders_by_session AS o USING (website_session_id)
                ON CONFLICT (website_session_id)
                DO UPDATE SET
                    date_key = EXCLUDED.date_key,
                    customer_key = EXCLUDED.customer_key,
                    marketing_key = EXCLUDED.marketing_key,
                    device_key = EXCLUDED.device_key,
                    session_started_at = EXCLUDED.session_started_at,
                    landing_page_url = EXCLUDED.landing_page_url,
                    exit_page_url = EXCLUDED.exit_page_url,
                    pageview_count = EXCLUDED.pageview_count,
                    duration_seconds = EXCLUDED.duration_seconds,
                    is_repeat_session = EXCLUDED.is_repeat_session,
                    is_bounce = EXCLUDED.is_bounce,
                    is_converted = EXCLUDED.is_converted,
                    order_count = EXCLUDED.order_count,
                    items_purchased = EXCLUDED.items_purchased,
                    revenue_usd = EXCLUDED.revenue_usd,
                    gross_profit_usd = EXCLUDED.gross_profit_usd
                """
            )
        )
    return result.rowcount
