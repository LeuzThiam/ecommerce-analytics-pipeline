from sqlalchemy import text
from sqlalchemy.engine import Engine


def build_dim_product(engine: Engine) -> int:
    """Construit ``warehouse.dim_product`` depuis le catalogue de staging.

    La clé ``product_key`` est une clé technique propre au warehouse tandis
    que ``product_id`` conserve l'identifiant métier de la source. L'UPSERT
    rend le chargement idempotent et propage les corrections de libellé ou de
    date sans créer une seconde ligne pour le même produit.
    """
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.dim_product (
                    product_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    product_id INTEGER NOT NULL UNIQUE,
                    product_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                INSERT INTO warehouse.dim_product (
                    product_id,
                    product_name,
                    created_at
                )
                SELECT
                    product_id,
                    product_name,
                    created_at
                FROM staging.products
                ON CONFLICT (product_id)
                DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    created_at = EXCLUDED.created_at
                """
            )
        )
    return result.rowcount
