import pandas as pd


def transform_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["product_name"] = df["product_name"].str.strip()
    return df