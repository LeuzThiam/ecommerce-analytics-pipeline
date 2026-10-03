import pandas as pd


def not_null(df: pd.DataFrame, column: str) -> pd.Series:
    """Indique pour chaque ligne si la colonne contient une valeur."""
    return df[column].notna()


def is_unique(df: pd.DataFrame, column: str) -> pd.Series:
    """Conserve la première occurrence et signale les doublons suivants."""
    return ~df[column].duplicated(keep="first")


def is_non_negative(df: pd.DataFrame, column: str) -> pd.Series:
    """Vérifie qu'une valeur numérique est supérieure ou égale à zéro."""
    return df[column] >= 0

def is_positive(df: pd.DataFrame, column: str) -> pd.Series:
    """Vérifie qu'une valeur numérique est strictement positive."""
    return df[column] > 0

def split_valid_invalid(df: pd.DataFrame, *masks: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sépare les lignes respectant toutes les règles de celles à rejeter."""
    # Une ligne est valide uniquement si toutes les règles sont vraies.
    combined_mask = pd.concat(masks, axis=1).all(axis=1)
    valid = df[combined_mask]
    rejected = df[~combined_mask]
    return valid, rejected

def is_in_set(df: pd.DataFrame, column: str, allowed_values: set) -> pd.Series:
    """Vérifie l'appartenance de chaque valeur à un référentiel autorisé."""
    return df[column].isin(allowed_values)

def not_empty_string(df: pd.DataFrame, column: str) -> pd.Series:
    """Refuse les chaînes vides ou composées uniquement d'espaces."""
    return df[column].astype(str).str.strip() != ""
