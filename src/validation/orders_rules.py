import pandas as pd


from .common_rules import not_null, is_unique, is_non_negative, split_valid_invalid, is_positive

def validate_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valide les identifiants, quantités et montants des commandes."""
    masks = [
        is_unique(df, "order_id"),
        not_null(df, "website_session_id"),
        not_null(df, "user_id"),
        is_positive(df, "items_purchased"),
        is_non_negative(df, "price_usd"),
        is_non_negative(df, "cogs_usd"),
    ]
    return split_valid_invalid(df, *masks)
