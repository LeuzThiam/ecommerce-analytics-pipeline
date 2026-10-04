from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task


@dag(
    dag_id="ecommerce_analytics_pipeline",
    description="Pipeline e-commerce multi-source vers le warehouse analytique",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ecommerce", "etl", "warehouse"],
)
def ecommerce_analytics_pipeline():
    """Planifie le pipeline existant sans dupliquer sa logique métier."""

    @task(execution_timeout=timedelta(minutes=90))
    def preflight() -> bool:
        """Échoue rapidement si la configuration ou les sources manquent."""
        from src.main import DATA_SOURCE_DIR
        from src.orchestration.preflight import validate_runtime_configuration

        validate_runtime_configuration(DATA_SOURCE_DIR)
        return True

    @task(execution_timeout=timedelta(hours=3))
    def run_pipeline(configuration_is_valid: bool) -> str:
        """Exécute l'ETL, le warehouse, les marts et la réconciliation."""
        if not configuration_is_valid:
            raise RuntimeError("Le contrôle préalable Airflow a échoué")

        from src.main import run

        return run()

    run_pipeline(preflight())


ecommerce_analytics_pipeline()
