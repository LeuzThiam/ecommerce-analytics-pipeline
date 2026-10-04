import os
from pathlib import Path


REQUIRED_ENVIRONMENT_VARIABLES = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)

REQUIRED_SOURCE_FILES = (
    "website_sessions.csv",
    "website_pageviews.csv",
    "products.json",
)


def validate_runtime_configuration(data_source_dir: Path) -> None:
    """Vérifie la configuration indispensable avant une exécution planifiée.

    Le contrôle ne journalise jamais les valeurs des variables, car certaines
    contiennent des secrets. Il signale uniquement les noms absents.
    """
    missing_variables = [
        name for name in REQUIRED_ENVIRONMENT_VARIABLES if not os.getenv(name)
    ]
    if missing_variables:
        missing = ", ".join(missing_variables)
        raise RuntimeError(f"Variables d'environnement manquantes : {missing}")

    missing_files = [
        filename
        for filename in REQUIRED_SOURCE_FILES
        if not (data_source_dir / filename).is_file()
    ]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(f"Fichiers sources manquants : {missing}")
