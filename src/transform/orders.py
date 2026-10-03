import pandas as pd


def transform_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les commandes et calcule leur marge brute."""
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["price_usd"] = df["price_usd"].astype(float)
    df["cogs_usd"] = df["cogs_usd"].astype(float)
    # La marge brute est calculée avant le chargement pour rester réutilisable.
    df["gross_profit"] = df["price_usd"] - df["cogs_usd"]
    return df
