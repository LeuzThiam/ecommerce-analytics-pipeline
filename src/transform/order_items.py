import pandas as pd


def transform_order_items(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les articles commandés et calcule leur marge brute."""
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["price_usd"] = df["price_usd"].astype(float)
    df["cogs_usd"] = df["cogs_usd"].astype(float)
    # Le grain de cette marge est l'article commandé, pas la commande entière.
    df["gross_profit"] = df["price_usd"] - df["cogs_usd"]
    return df
