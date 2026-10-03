import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def quarantine_rejected_rows(
    df: pd.DataFrame,
    source_name: str,
    run_id: str,
    output_dir: Path,
) -> Path | None:
    """Conserve les lignes invalides dans un CSV propre à l'exécution.

    Les lots successifs d'une même source sont ajoutés au même fichier. Les
    noms sont validés avant de construire le chemin afin d'empêcher toute
    écriture en dehors du répertoire de quarantaine.
    """
    if df.empty:
        return None

    _validate_filename_part(source_name, "source_name")
    _validate_filename_part(run_id, "run_id")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_name}_{run_id}.csv"
    file_exists = output_path.exists()

    rejected = df.copy()
    rejected["_pipeline_run_id"] = run_id
    rejected["_rejected_at"] = datetime.now(UTC).isoformat()
    rejected.to_csv(
        output_path,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False,
    )
    return output_path


def _validate_filename_part(value: str, field_name: str) -> None:
    """Valide une partie de nom de fichier générée par le pipeline."""
    if not value or SAFE_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Invalid {field_name} for quarantine file: {value!r}")
