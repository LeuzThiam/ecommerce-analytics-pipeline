from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_dim_customer(engine: Engine) -> int:
    """Construit une ligne par utilisateur dans ``warehouse.dim_customer``.

    Les sessions constituent la source principale des utilisateurs. Une union
    complète avec les commandes protège néanmoins le warehouse contre une
    éventuelle commande dont l'utilisateur serait absent des sessions.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
                    customer_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id BIGINT NOT NULL UNIQUE,
                    first_session_at TIMESTAMP,
                    last_session_at TIMESTAMP,
                    first_order_at TIMESTAMP,
                    has_repeat_session BOOLEAN NOT NULL,
                    is_buyer BOOLEAN NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                WITH session_customers AS (
                    SELECT
                        user_id,
                        MIN(created_at) AS first_session_at,
                        MAX(created_at) AS last_session_at,
                        BOOL_OR(is_repeat_session = 1) AS has_repeat_session
                    FROM staging.website_sessions
                    GROUP BY user_id
                ),
                order_customers AS (
                    SELECT
                        user_id,
                        MIN(created_at) AS first_order_at
                    FROM staging.orders
                    GROUP BY user_id
                )
                INSERT INTO warehouse.dim_customer (
                    user_id,
                    first_session_at,
                    last_session_at,
                    first_order_at,
                    has_repeat_session,
                    is_buyer
                )
                SELECT
                    COALESCE(s.user_id, o.user_id),
                    s.first_session_at,
                    s.last_session_at,
                    o.first_order_at,
                    COALESCE(s.has_repeat_session, FALSE),
                    o.user_id IS NOT NULL
                FROM session_customers AS s
                FULL OUTER JOIN order_customers AS o USING (user_id)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    first_session_at = EXCLUDED.first_session_at,
                    last_session_at = EXCLUDED.last_session_at,
                    first_order_at = EXCLUDED.first_order_at,
                    has_repeat_session = EXCLUDED.has_repeat_session,
                    is_buyer = EXCLUDED.is_buyer
                """
            )
        )
    return result.rowcount
