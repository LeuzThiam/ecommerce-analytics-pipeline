import pandas as pd

from src.validation.common_rules import is_in_set, is_non_negative, is_unique, split_valid_invalid


def validate_refunds(
    df: pd.DataFrame, valid_order_item_ids: set, valid_order_ids: set
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valide les remboursements et leurs relations avec le staging.

    Un remboursement doit correspondre à un article et à une commande connus,
    et son montant ne peut pas être négatif.
    """
    masks = [
        is_unique(df, "order_item_refund_id"),
        is_in_set(df, "order_item_id", valid_order_item_ids),
        is_in_set(df, "order_id", valid_order_ids),
        is_non_negative(df, "refund_amount_usd"),
    ]
    return split_valid_invalid(df, *masks)
