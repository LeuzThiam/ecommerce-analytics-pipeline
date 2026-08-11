# E-commerce Analytics Data Platform

Pipeline ETL multi-source construit en Python : extraction depuis 4 types de sources hétérogènes (CSV, JSON, API REST, PostgreSQL), validation, transformation et chargement dans un entrepôt PostgreSQL — avec logging, tests automatisés et orchestration en une seule commande.

Projet réalisé en 3 versions progressives :

- **V1 — Multi-Source ETL** *(terminée)* : extraction, validation, transformation et chargement en staging.
- **V2 — Incremental & Reliable ETL** *(à venir)* : checkpoints, idempotence, transactions, retry.
- **V3 — Automated Analytics Warehouse** *(à venir)* : star schema, data marts, réconciliation.

## Le problème

Une entreprise e-commerce reçoit ses données depuis plusieurs systèmes qui ne parlent pas le même langage : des fichiers CSV, une API REST, une base PostgreSQL externe. Avant de pouvoir analyser quoi que ce soit, il faut un pipeline capable d'aller chercher ces données là où elles sont, de vérifier leur qualité, de les uniformiser, et de les charger dans un seul endroit fiable.

## Architecture

```
                SOURCES
 CSV ──────┐
 JSON ─────┤
 API ──────┼────→ EXTRACT ──→ VALIDATE ──→ TRANSFORM ──→ LOAD
 SQL ──────┘                                                │
                                                             ↓
                                                   PostgreSQL (staging)
```

Chaque type de source a son propre extracteur (`src/extract/`), chaque entité a ses propres règles de validation (`src/validation/`) et sa propre transformation (`src/transform/`), et un loader générique unique (`src/load/`) écrit le résultat dans PostgreSQL. `src/main.py` orchestre l'ensemble.

## Stack technique

| Composant | Outil |
|---|---|
| Traitement de données | Python, Pandas |
| API REST | FastAPI, Uvicorn |
| Base de données | PostgreSQL, SQLAlchemy |
| Tests | pytest |
| Logging | module `logging` (console + fichier) |

## Résultats (V1)

Le pipeline traite ~1,7 million de lignes au total, réparties sur 6 entités, avec un taux de rejet de 0% sur ce jeu de données :

| Entité | Source | Lignes chargées |
|---|---|---|
| website_sessions | CSV | 472 871 |
| website_pageviews | CSV | 1 188 124 |
| products | JSON | 4 |
| orders | API REST | 32 313 |
| order_items | PostgreSQL | 40 025 |
| order_item_refunds | PostgreSQL | 1 731 |

## Structure du projet

```
ecommerce-analytics-pipeline/
├── data/
│   ├── source/          # sources fichiers (CSV, JSON) — non versionné, voir Installation
│   └── rejected/         # lignes rejetées par la validation
├── src/
│   ├── extract/           # un extracteur par type de source (CSV, JSON, API, SQL)
│   ├── validation/        # règles de validation par entité + règles génériques réutilisables
│   ├── transform/          # une transformation par entité (dates, types, mesures calculées)
│   ├── load/               # chargement générique vers PostgreSQL
│   └── main.py              # orchestration du pipeline complet
├── api/
│   └── orders_api.py    # API REST locale simulant la source "orders"
├── tests/                # suite de tests pytest
└── logs/                 # logs d'exécution du pipeline
```

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copier `.env.example` vers `.env` et renseigner les paramètres de connexion PostgreSQL.

Créer la base de données et les schémas :

```sql
CREATE DATABASE ecommerce_analytics;
-- puis, connecté sur ecommerce_analytics :
CREATE SCHEMA source;
CREATE SCHEMA staging;
CREATE SCHEMA warehouse;
CREATE SCHEMA marts;
CREATE SCHEMA control;
```

Placer les fichiers sources (`website_sessions.csv`, `website_pageviews.csv`, `products.json`, `orders.csv`) dans `data/source/`, et importer `order_items`/`order_item_refunds` dans le schéma `source` de PostgreSQL.

## Lancer le pipeline

Démarrer l'Orders API (dans un terminal séparé) :

```bash
uvicorn api.orders_api:app --reload --port 8000
```

Puis exécuter le pipeline complet :

```bash
python -m src.main
```

## Tests

```bash
pytest -v
```

## Prochaines étapes

- V2 : chargement incrémental basé sur des checkpoints, UPSERT idempotent, gestion des pannes
- V3 : star schema (`fact_sales`, `fact_sessions`), data marts, réconciliation source ↔ entrepôt