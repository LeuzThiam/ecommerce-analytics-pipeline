from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_funnel_performance(engine: Engine) -> int:
    """Construit le funnel e-commerce quotidien au grain session.

    Les URL sont d'abord transformées en indicateurs par session. Cette étape
    garantit qu'une même session n'est comptée qu'une fois à chaque niveau du
    funnel, quel que soit son nombre de pages vues.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS marts.funnel_performance (
                    date_key INTEGER PRIMARY KEY
                        REFERENCES warehouse.dim_date(date_key),
                    date DATE NOT NULL UNIQUE,
                    sessions INTEGER NOT NULL,
                    product_list_sessions INTEGER NOT NULL,
                    product_detail_sessions INTEGER NOT NULL,
                    cart_sessions INTEGER NOT NULL,
                    shipping_sessions INTEGER NOT NULL,
                    billing_sessions INTEGER NOT NULL,
                    order_sessions INTEGER NOT NULL,
                    product_view_rate NUMERIC(8, 4) NOT NULL,
                    product_click_rate NUMERIC(8, 4) NOT NULL,
                    cart_rate NUMERIC(8, 4) NOT NULL,
                    shipping_rate NUMERIC(8, 4) NOT NULL,
                    billing_rate NUMERIC(8, 4) NOT NULL,
                    checkout_rate NUMERIC(8, 4) NOT NULL,
                    conversion_rate NUMERIC(8, 4) NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH page_steps_by_session AS (
                    SELECT
                        website_session_id,
                        BOOL_OR(pageview_url = '/products') AS viewed_product_list,
                        BOOL_OR(
                            pageview_url IN (
                                '/the-original-mr-fuzzy',
                                '/the-forever-love-bear',
                                '/the-birthday-sugar-panda',
                                '/the-hudson-river-mini-bear'
                            )
                        ) AS viewed_product_detail,
                        BOOL_OR(pageview_url = '/cart') AS viewed_cart,
                        BOOL_OR(pageview_url = '/shipping') AS viewed_shipping,
                        BOOL_OR(
                            pageview_url IN ('/billing', '/billing-2')
                        ) AS viewed_billing
                    FROM staging.website_pageviews
                    GROUP BY website_session_id
                ),
                funnel_by_date AS (
                    SELECT
                        s.date_key,
                        COUNT(*)::integer AS sessions,
                        COUNT(*) FILTER (
                            WHERE p.viewed_product_list
                        )::integer AS product_list_sessions,
                        COUNT(*) FILTER (
                            WHERE p.viewed_product_detail
                        )::integer AS product_detail_sessions,
                        COUNT(*) FILTER (
                            WHERE p.viewed_cart
                        )::integer AS cart_sessions,
                        COUNT(*) FILTER (
                            WHERE p.viewed_shipping
                        )::integer AS shipping_sessions,
                        COUNT(*) FILTER (
                            WHERE p.viewed_billing
                        )::integer AS billing_sessions,
                        COUNT(*) FILTER (
                            WHERE s.is_converted
                        )::integer AS order_sessions
                    FROM warehouse.fact_sessions AS s
                    JOIN page_steps_by_session AS p USING (website_session_id)
                    GROUP BY s.date_key
                ),
                funnel_values AS (
                    SELECT
                        d.date_key,
                        d.date,
                        COALESCE(f.sessions, 0) AS sessions,
                        COALESCE(f.product_list_sessions, 0) AS product_list_sessions,
                        COALESCE(f.product_detail_sessions, 0) AS product_detail_sessions,
                        COALESCE(f.cart_sessions, 0) AS cart_sessions,
                        COALESCE(f.shipping_sessions, 0) AS shipping_sessions,
                        COALESCE(f.billing_sessions, 0) AS billing_sessions,
                        COALESCE(f.order_sessions, 0) AS order_sessions
                    FROM warehouse.dim_date AS d
                    LEFT JOIN funnel_by_date AS f USING (date_key)
                )
                INSERT INTO marts.funnel_performance (
                    date_key,
                    date,
                    sessions,
                    product_list_sessions,
                    product_detail_sessions,
                    cart_sessions,
                    shipping_sessions,
                    billing_sessions,
                    order_sessions,
                    product_view_rate,
                    product_click_rate,
                    cart_rate,
                    shipping_rate,
                    billing_rate,
                    checkout_rate,
                    conversion_rate
                )
                SELECT
                    date_key,
                    date,
                    sessions,
                    product_list_sessions,
                    product_detail_sessions,
                    cart_sessions,
                    shipping_sessions,
                    billing_sessions,
                    order_sessions,
                    COALESCE(
                        ROUND(product_list_sessions::numeric / NULLIF(sessions, 0), 4),
                        0
                    ),
                    COALESCE(
                        ROUND(
                            product_detail_sessions::numeric
                            / NULLIF(product_list_sessions, 0),
                            4
                        ),
                        0
                    ),
                    COALESCE(
                        ROUND(
                            cart_sessions::numeric
                            / NULLIF(product_detail_sessions, 0),
                            4
                        ),
                        0
                    ),
                    COALESCE(
                        ROUND(
                            shipping_sessions::numeric / NULLIF(cart_sessions, 0),
                            4
                        ),
                        0
                    ),
                    COALESCE(
                        ROUND(
                            billing_sessions::numeric
                            / NULLIF(shipping_sessions, 0),
                            4
                        ),
                        0
                    ),
                    COALESCE(
                        ROUND(
                            order_sessions::numeric / NULLIF(billing_sessions, 0),
                            4
                        ),
                        0
                    ),
                    COALESCE(
                        ROUND(order_sessions::numeric / NULLIF(sessions, 0), 4),
                        0
                    )
                FROM funnel_values
                ON CONFLICT (date_key)
                DO UPDATE SET
                    date = EXCLUDED.date,
                    sessions = EXCLUDED.sessions,
                    product_list_sessions = EXCLUDED.product_list_sessions,
                    product_detail_sessions = EXCLUDED.product_detail_sessions,
                    cart_sessions = EXCLUDED.cart_sessions,
                    shipping_sessions = EXCLUDED.shipping_sessions,
                    billing_sessions = EXCLUDED.billing_sessions,
                    order_sessions = EXCLUDED.order_sessions,
                    product_view_rate = EXCLUDED.product_view_rate,
                    product_click_rate = EXCLUDED.product_click_rate,
                    cart_rate = EXCLUDED.cart_rate,
                    shipping_rate = EXCLUDED.shipping_rate,
                    billing_rate = EXCLUDED.billing_rate,
                    checkout_rate = EXCLUDED.checkout_rate,
                    conversion_rate = EXCLUDED.conversion_rate
                """
            )
        )
    return result.rowcount
