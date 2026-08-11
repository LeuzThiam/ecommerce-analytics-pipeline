# E-commerce Analytics Data Platform

Pipeline multi-source (CSV, JSON, API REST, PostgreSQL) construit en 3 versions :

- **V1 — Multi-Source ETL** : extraction depuis 4 types de sources, validation, chargement en staging.
- **V2 — Incremental & Reliable ETL** : checkpoints, idempotence, transactions, retry.
- **V3 — Automated Analytics Warehouse** : star schema, data marts, réconciliation.

## Structure

```
ecommerce-analytics-pipeline/
├── data/
│   ├── source/      # sources fichiers (CSV, JSON) utilisées par le pipeline
│   └── rejected/     # lignes rejetées par la validation
├── src/
│   ├── extract/       # un extracteur par type de source
│   ├── transform/      # une transformation par entité
│   ├── validation/     # règles de validation par entité
│   ├── load/          # chargement vers PostgreSQL
│   ├── config.py
│   └── main.py
├── api/
│   └── orders_api.py  # API REST locale simulant la source "orders"
├── tests/
└── logs/
```

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copier `.env.example` vers `.env` et renseigner les paramètres de connexion PostgreSQL.
