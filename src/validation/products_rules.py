import pandas as pd

from src.validation.common_rules import is_unique, not_empty_string, not_null, split_valid_invalid


def validate_products(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valide l'unicité, le nom et la date de création des produits."""
    masks = [
        is_unique(df, "product_id"),
        not_empty_string(df, "product_name"),
        not_null(df, "created_at"),
    ]
    return split_valid_invalid(df, *masks)
