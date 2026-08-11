import pandas as pd

from src.validation.common_rules import is_unique, not_empty_string, not_null, split_valid_invalid


def validate_pageviews(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    masks = [
        is_unique(df, "website_pageview_id"),
        not_null(df, "website_session_id"),
        not_empty_string(df, "pageview_url"),
        not_null(df, "created_at"),
    ]
    return split_valid_invalid(df, *masks)