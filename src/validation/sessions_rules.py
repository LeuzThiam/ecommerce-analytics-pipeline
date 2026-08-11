import pandas as pd

from .common_rules import is_in_set, is_unique, not_null, split_valid_invalid

VALID_DEVICE_TYPES = {"desktop", "mobile"}


def validate_sessions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    masks = [
        not_null(df, "website_session_id"),
        is_unique(df, "website_session_id"),
        not_null(df, "user_id"),
        is_in_set(df, "device_type", VALID_DEVICE_TYPES),
    ]
    return split_valid_invalid(df, *masks)