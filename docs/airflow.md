# Orchestration avec Airflow

## Rôle

Airflow planifie et supervise le pipeline sans contenir sa logique métier. Le
DAG exécute d'abord un contrôle de configuration, puis appelle le même point
d'entrée Python que l'exécution manuelle. Les extractions, validations,
transactions, constructions du warehouse, marts et réconciliations restent
donc testables en dehors d'Airflow.

## Pourquoi Docker sous Windows

Airflow s'exécute sur un environnement Linux. Le projet utilise son image
officielle dans Docker afin de ne pas installer Airflow dans l'environnement
virtuel Python principal et de conserver des dépendances isolées.

## Prérequis

- Docker Desktop avec les conteneurs Linux ;
- PostgreSQL accessible depuis Docker ;
- l'API Orders démarrée sur la machine hôte ;
- le fichier `.env` configuré ;
- les trois fichiers sources présents dans `data/source/`.

Par défaut, le conteneur contacte PostgreSQL et l'API locale avec
`host.docker.internal`. Ces valeurs peuvent être remplacées avec
`AIRFLOW_POSTGRES_HOST` et `AIRFLOW_ORDERS_API_BASE_URL`.

## Démarrage

Depuis la racine du projet :

```bash
docker compose -f docker-compose.airflow.yml up --build
```

L'interface est ensuite disponible sur `http://localhost:8080`. La commande
`standalone` affiche les identifiants locaux dans les journaux du conteneur.

## Planification et sécurité

Le DAG `ecommerce_analytics_pipeline` est planifié chaque jour à 02:00 UTC. Il
désactive le rattrapage historique, limite le pipeline à une exécution active,
effectue deux nouvelles tentatives espacées de cinq minutes et applique des
durées maximales aux tâches.

Le contrôle préalable vérifie les variables PostgreSQL et les fichiers sources
sans afficher la valeur des secrets. Le statut final reste enregistré dans
`control.pipeline_runs` par le pipeline existant.

## Arrêt

```bash
docker compose -f docker-compose.airflow.yml down
```

Pour supprimer également les métadonnées Airflow locales :

```bash
docker compose -f docker-compose.airflow.yml down --volumes
```
