import pandas as pd

def transform_pageviews(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df