from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_dim_marketing(engine: Engine) -> int:
    """Construit les combinaisons d'acquisition de ``dim_marketing``.

    Les valeurs absentes reçoivent un libellé explicite. Cette normalisation
    permet d'imposer une clé métier unique, car PostgreSQL considère autrement
    deux valeurs ``NULL`` comme distinctes dans une contrainte d'unicité.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.dim_marketing (
                    marketing_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    utm_source VARCHAR(100) NOT NULL,
                    utm_campaign VARCHAR(100) NOT NULL,
                    utm_content VARCHAR(255) NOT NULL,
                    http_referer VARCHAR(500) NOT NULL,
                    is_direct BOOLEAN NOT NULL,
                    UNIQUE (utm_source, utm_campaign, utm_content, http_referer)
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                INSERT INTO warehouse.dim_marketing (
                    utm_source,
                    utm_campaign,
                    utm_content,
                    http_referer,
                    is_direct
                )
                SELECT DISTINCT
                    COALESCE(utm_source, '(non renseigné)'),
                    COALESCE(utm_campaign, '(non renseignée)'),
                    COALESCE(utm_content, '(non renseigné)'),
                    COALESCE(http_referer, '(aucun)'),
                    utm_source IS NULL
                        AND utm_campaign IS NULL
                        AND utm_content IS NULL
                        AND http_referer IS NULL
                FROM staging.website_sessions
                ON CONFLICT (
                    utm_source,
                    utm_campaign,
                    utm_content,
                    http_referer
                )
                DO UPDATE SET
                    is_direct = EXCLUDED.is_direct
                """
            )
        )
    return result.rowcount
