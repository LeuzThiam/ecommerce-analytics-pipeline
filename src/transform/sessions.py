import pandas as pd

def transform_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les dates et les attributs marketing des sessions."""
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    # La casse et les espaces ne doivent pas créer de catégories distinctes.
    for column in ["utm_source", "utm_campaign", "utm_content", "device_type"]:
        df[column] = df[column].str.strip().str.lower()

    return df
