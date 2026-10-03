from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_dim_device(engine: Engine) -> int:
    """Construit ``warehouse.dim_device`` depuis les types de session.

    Le code source est conservé comme clé métier. Le libellé français et
    l'indicateur mobile centralisent la logique de présentation afin que les
    futures analyses ne la répètent pas.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.dim_device (
                    device_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    device_type VARCHAR(50) NOT NULL UNIQUE,
                    device_label VARCHAR(50) NOT NULL,
                    is_mobile BOOLEAN NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                INSERT INTO warehouse.dim_device (
                    device_type,
                    device_label,
                    is_mobile
                )
                SELECT DISTINCT
                    device_type,
                    CASE device_type
                        WHEN 'desktop' THEN 'ordinateur'
                        WHEN 'mobile' THEN 'mobile'
                        ELSE device_type
                    END,
                    device_type = 'mobile'
                FROM staging.website_sessions
                ON CONFLICT (device_type)
                DO UPDATE SET
                    device_label = EXCLUDED.device_label,
                    is_mobile = EXCLUDED.is_mobile
                """
            )
        )
    return result.rowcount
