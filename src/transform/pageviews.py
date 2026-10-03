import pandas as pd

def transform_pageviews(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit la date des pages consultées dans un type temporel fiable."""
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df
