import pandas as pd

from src.analysis.report import (
    analyse_customers,
    analyse_funnel,
    analyse_marketing,
    analyse_sales,
)


def test_sales_analysis_aggregates_monthly_metrics():
    daily = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-02-01"],
            "sessions": [100, 200, 100],
            "orders": [10, 30, 20],
            "gross_revenue_usd": [1000, 3000, 2500],
            "refund_amount_usd": [50, 100, 0],
            "net_revenue_usd": [950, 2900, 2500],
            "net_profit_usd": [400, 1200, 1000],
        }
    )

    result = analyse_sales(daily)

    assert result["month"].tolist() == ["2026-01", "2026-02"]
    assert result.loc[0, "net_revenue_usd"] == 3850
    assert result.loc[0, "conversion_rate"] == 40 / 300


def test_customer_analysis_preserves_prospects_without_revenue():
    customers = pd.DataFrame(
        {
            "customer_status": ["prospect", "acheteur", "acheteur"],
            "user_id": [1, 2, 3],
            "order_count": [0, 1, 2],
            "lifetime_revenue_usd": [0, 50, 150],
            "lifetime_profit_usd": [0, 20, 60],
        }
    )

    result = analyse_customers(customers)

    prospect = result.loc[result["customer_status"] == "prospect"].iloc[0]
    assert prospect["customers"] == 1
    assert prospect["revenue_per_customer_usd"] == 0


def test_funnel_analysis_recalculates_weighted_rates():
    funnel = pd.DataFrame(
        {
            "sessions": [100, 300],
            "product_list_sessions": [80, 180],
            "product_detail_sessions": [40, 90],
            "cart_sessions": [20, 45],
            "shipping_sessions": [10, 30],
            "billing_sessions": [8, 24],
            "order_sessions": [5, 15],
        }
    )

    result = analyse_funnel(funnel)

    assert result.loc[result["stage"] == "Commande", "sessions"].item() == 20
    assert result.loc[result["stage"] == "Commande", "rate_from_start"].item() == 0.05


def test_marketing_analysis_groups_same_channel_before_calculating_rates():
    marketing = pd.DataFrame(
        {
            "utm_source": ["gsearch", "gsearch"],
            "utm_campaign": ["brand", "brand"],
            "is_direct": [False, False],
            "sessions": [100, 300],
            "orders": [20, 30],
            "net_revenue_usd": [1000, 2000],
            "net_profit_usd": [400, 800],
        }
    )

    result = analyse_marketing(marketing)

    assert len(result) == 1
    assert result.loc[0, "conversion_rate"] == 50 / 400
    assert result.loc[0, "revenue_per_session_usd"] == 3000 / 400
