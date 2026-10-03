import pandas as pd

from src.validation.common_rules import is_in_set, is_non_negative, is_unique, split_valid_invalid


def validate_order_items(
    df: pd.DataFrame, valid_order_ids: set, valid_product_ids: set
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valide les articles et leurs relations avec commandes et produits.

    Les ensembles d'identifiants représentent les référentiels déjà validés
    auxquels chaque article doit appartenir.
    """
    masks = [
        is_unique(df, "order_item_id"),
        is_in_set(df, "order_id", valid_order_ids),
        is_in_set(df, "product_id", valid_product_ids),
        is_non_negative(df, "price_usd"),
        is_non_negative(df, "cogs_usd"),
    ]
    return split_valid_invalid(df, *masks)
