import pandas as pd


def not_null(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column].notna()


def is_unique(df: pd.DataFrame, column: str) -> pd.Series:
    return ~df[column].duplicated(keep="first")


def is_non_negative(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column] >= 0

def is_positive(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column] > 0

def split_valid_invalid(df: pd.DataFrame, *masks: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    combined_mask = pd.concat(masks, axis=1).all(axis=1)
    valid = df[combined_mask]
    rejected = df[~combined_mask]
    return valid, rejected

def is_in_set(df: pd.DataFrame, column: str, allowed_values: set) -> pd.Series:
    return df[column].isin(allowed_values)

def not_empty_string(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column].astype(str).str.strip() != ""