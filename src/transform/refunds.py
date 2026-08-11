import pandas as pd


def transform_refunds(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["refund_amount_usd"] = df["refund_amount_usd"].astype(float)
    return df