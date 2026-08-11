import pandas as pd

def transform_sessions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    for column in ["utm_source", "utm_campaign", "utm_content", "device_type"]:
        df[column] = df[column].str.strip().str.lower()

    return df