import os
from pathlib import Path

import matplotlib
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# Le moteur sans interface graphique fonctionne en local, en CI et dans Airflow.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_OUTPUT_DIR = Path(__file__).parents[2] / "reports" / "analysis"

MART_QUERIES = {
    "sales": "SELECT * FROM marts.daily_performance ORDER BY date",
    "customers": "SELECT * FROM marts.customer_summary",
    "marketing": "SELECT * FROM marts.marketing_performance",
    "funnel": "SELECT * FROM marts.funnel_performance ORDER BY date",
    "products": "SELECT * FROM marts.product_performance",
}


def load_marts(engine: Engine) -> dict[str, pd.DataFrame]:
    """Charge les cinq marts nécessaires aux analyses finales."""
    return {
        name: pd.read_sql(text(query), engine)
        for name, query in MART_QUERIES.items()
    }


def analyse_sales(daily: pd.DataFrame) -> pd.DataFrame:
    """Agrège les ventes par mois pour analyser activité et rentabilité."""
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["month"] = frame["date"].dt.to_period("M").astype(str)
    return (
        frame.groupby("month", as_index=False)
        .agg(
            sessions=("sessions", "sum"),
            orders=("orders", "sum"),
            gross_revenue_usd=("gross_revenue_usd", "sum"),
            refund_amount_usd=("refund_amount_usd", "sum"),
            net_revenue_usd=("net_revenue_usd", "sum"),
            net_profit_usd=("net_profit_usd", "sum"),
        )
        .assign(
            conversion_rate=lambda data: data["orders"].div(
                data["sessions"].replace(0, pd.NA)
            ).fillna(0),
            average_order_value_usd=lambda data: data["gross_revenue_usd"].div(
                data["orders"].replace(0, pd.NA)
            ).fillna(0),
        )
    )


def analyse_customers(customers: pd.DataFrame) -> pd.DataFrame:
    """Compare les segments clients et leur contribution commerciale."""
    return (
        customers.groupby("customer_status", as_index=False)
        .agg(
            customers=("user_id", "count"),
            orders=("order_count", "sum"),
            lifetime_revenue_usd=("lifetime_revenue_usd", "sum"),
            lifetime_profit_usd=("lifetime_profit_usd", "sum"),
        )
        .assign(
            revenue_per_customer_usd=lambda data: data[
                "lifetime_revenue_usd"
            ].div(data["customers"].replace(0, pd.NA)).fillna(0)
        )
        .sort_values("lifetime_revenue_usd", ascending=False)
        .reset_index(drop=True)
    )


def analyse_marketing(marketing: pd.DataFrame) -> pd.DataFrame:
    """Classe les canaux selon leur trafic, conversion et revenu net."""
    return (
        marketing.groupby(
            ["utm_source", "utm_campaign", "is_direct"],
            as_index=False,
            dropna=False,
        )
        .agg(
            sessions=("sessions", "sum"),
            orders=("orders", "sum"),
            net_revenue_usd=("net_revenue_usd", "sum"),
            net_profit_usd=("net_profit_usd", "sum"),
        )
        .assign(
            conversion_rate=lambda data: data["orders"].div(
                data["sessions"].replace(0, pd.NA)
            ).fillna(0),
            revenue_per_session_usd=lambda data: data["net_revenue_usd"].div(
                data["sessions"].replace(0, pd.NA)
            ).fillna(0),
        )
        .sort_values(["net_revenue_usd", "sessions"], ascending=False)
        .reset_index(drop=True)
    )


def analyse_funnel(funnel: pd.DataFrame) -> pd.DataFrame:
    """Calcule les volumes et taux globaux de chaque étape du funnel."""
    stages = [
        ("Sessions", "sessions"),
        ("Liste produits", "product_list_sessions"),
        ("Fiche produit", "product_detail_sessions"),
        ("Panier", "cart_sessions"),
        ("Livraison", "shipping_sessions"),
        ("Facturation", "billing_sessions"),
        ("Commande", "order_sessions"),
    ]
    rows = []
    previous_volume = None
    initial_volume = int(funnel["sessions"].sum())
    for stage, column in stages:
        volume = int(funnel[column].sum())
        rows.append(
            {
                "stage": stage,
                "sessions": volume,
                "rate_from_previous": (
                    volume / previous_volume if previous_volume else 1.0
                ),
                "rate_from_start": volume / initial_volume if initial_volume else 0.0,
            }
        )
        previous_volume = volume
    return pd.DataFrame(rows)


def analyse_products(products: pd.DataFrame) -> pd.DataFrame:
    """Classe les produits selon ventes, profitabilité et remboursements."""
    columns = [
        "product_id",
        "product_name",
        "orders",
        "units_sold",
        "net_revenue_usd",
        "net_profit_usd",
        "gross_margin_rate",
        "refund_rate",
    ]
    return products[columns].sort_values(
        "net_revenue_usd", ascending=False
    ).reset_index(drop=True)


def build_analyses(marts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Construit les cinq analyses attendues à partir des marts chargés."""
    return {
        "sales_monthly": analyse_sales(marts["sales"]),
        "customer_segments": analyse_customers(marts["customers"]),
        "marketing_channels": analyse_marketing(marts["marketing"]),
        "funnel_overall": analyse_funnel(marts["funnel"]),
        "product_performance": analyse_products(marts["products"]),
    }


def _save_chart(data: pd.DataFrame, name: str, output_dir: Path) -> None:
    """Génère un graphique adapté à l'analyse demandée."""
    figure, axis = plt.subplots(figsize=(10, 5.5))

    if name == "sales_monthly":
        axis.plot(data["month"], data["net_revenue_usd"], color="#1F4E78")
        axis.set_ylabel("Revenu net (USD)")
        axis.tick_params(axis="x", rotation=60)
        title = "Évolution mensuelle du revenu net"
    elif name == "customer_segments":
        axis.bar(data["customer_status"], data["lifetime_revenue_usd"], color="#4472C4")
        axis.set_ylabel("Revenu client cumulé (USD)")
        title = "Contribution des segments clients"
    elif name == "marketing_channels":
        labels = (
            data["utm_source"].fillna("direct")
            + " / "
            + data["utm_campaign"].fillna("sans campagne")
            + data["is_direct"].map({True: " / direct", False: ""})
        )
        axis.barh(labels, data["net_revenue_usd"], color="#70AD47")
        axis.set_xlabel("Revenu net (USD)")
        axis.invert_yaxis()
        title = "Performance des canaux marketing"
    elif name == "funnel_overall":
        axis.bar(data["stage"], data["sessions"], color="#ED7D31")
        axis.set_ylabel("Sessions")
        axis.tick_params(axis="x", rotation=35)
        title = "Funnel de conversion global"
    else:
        axis.barh(data["product_name"], data["net_profit_usd"], color="#5B9BD5")
        axis.set_xlabel("Profit net (USD)")
        axis.invert_yaxis()
        title = "Profitabilité par produit"

    axis.set_title(title)
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / f"{name}.png", dpi=150)
    plt.close(figure)


def export_analyses(
    analyses: dict[str, pd.DataFrame],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    """Exporte chaque analyse en CSV et en graphique PNG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in analyses.items():
        data.to_csv(output_dir / f"{name}.csv", index=False)
        _save_chart(data, name, output_dir)
    (output_dir / "README.md").write_text(
        build_markdown_summary(analyses),
        encoding="utf-8",
    )


def build_markdown_summary(analyses: dict[str, pd.DataFrame]) -> str:
    """Présente les principaux constats issus des résultats calculés."""
    sales = analyses["sales_monthly"]
    customers = analyses["customer_segments"]
    marketing = analyses["marketing_channels"]
    funnel = analyses["funnel_overall"]
    products = analyses["product_performance"]

    peak_month = sales.loc[sales["net_revenue_usd"].idxmax()]
    repeat_customers = customers.loc[
        customers["customer_status"] == "acheteur récurrent"
    ].iloc[0]
    top_channel = marketing.iloc[0]
    top_channel_name = f"{top_channel['utm_source']} / {top_channel['utm_campaign']}"
    conversion = funnel.iloc[-1]
    top_product = products.iloc[0]

    return f"""# Résultats des analyses Python

Ces résultats ont été générés depuis les marts PostgreSQL par
`python -m src.analysis.report`.

## Constats principaux

- Le meilleur mois est **{peak_month['month']}** avec un revenu net de
  **{peak_month['net_revenue_usd']:,.2f} USD**.
- Les **{int(repeat_customers['customers']):,} acheteurs récurrents** génèrent
  en moyenne **{repeat_customers['revenue_per_customer_usd']:,.2f} USD** par
  client.
- Le premier canal en revenu net est **{top_channel_name}**, avec
  **{top_channel['net_revenue_usd']:,.2f} USD**.
- Le funnel convertit **{conversion['rate_from_start']:.2%}** des sessions en
  commandes.
- Le produit le plus rentable est **{top_product['product_name']}**, avec un
  profit net de **{top_product['net_profit_usd']:,.2f} USD**.

## Livrables

Chaque thème est disponible en CSV pour l'inspection des valeurs et en PNG
pour la visualisation : ventes mensuelles, segments clients, canaux marketing,
funnel global et performance produit.
"""


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, pd.DataFrame]:
    """Charge le warehouse puis produit toutes les analyses finales."""
    load_dotenv()
    database_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:"
        f"{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    analyses = build_analyses(load_marts(create_engine(database_url)))
    export_analyses(analyses, output_dir)
    return analyses


if __name__ == "__main__":
    run()
