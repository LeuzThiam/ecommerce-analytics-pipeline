from pathlib import Path

import pytest

from src.orchestration.preflight import (
    REQUIRED_ENVIRONMENT_VARIABLES,
    REQUIRED_SOURCE_FILES,
    validate_runtime_configuration,
)


def test_preflight_accepts_complete_configuration(tmp_path, monkeypatch):
    """Le contrôle accepte des variables et fichiers sources complets."""
    for name in REQUIRED_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(name, "configured")
    for filename in REQUIRED_SOURCE_FILES:
        (tmp_path / filename).touch()

    validate_runtime_configuration(tmp_path)


def test_preflight_reports_names_without_exposing_values(tmp_path, monkeypatch):
    """Une variable absente est nommée sans révéler les autres secrets."""
    for name in REQUIRED_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(name, "secret-value")
    monkeypatch.delenv("POSTGRES_PASSWORD")

    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD") as error:
        validate_runtime_configuration(tmp_path)

    assert "secret-value" not in str(error.value)


def test_preflight_reports_missing_source_files(tmp_path, monkeypatch):
    """Le contrôle liste les fichiers requis absents avant le démarrage."""
    for name in REQUIRED_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(name, "configured")

    with pytest.raises(FileNotFoundError, match="website_sessions.csv"):
        validate_runtime_configuration(tmp_path)


def test_airflow_dag_has_safe_scheduling_options():
    """Le DAG évite le rattrapage et les exécutions concurrentes."""
    dag_path = Path("dags/ecommerce_analytics_pipeline.py")
    source = dag_path.read_text(encoding="utf-8")

    assert 'schedule="0 2 * * *"' in source
    assert "catchup=False" in source
    assert "max_active_runs=1" in source
    assert '"retries": 2' in source
    assert "validate_runtime_configuration" in source
