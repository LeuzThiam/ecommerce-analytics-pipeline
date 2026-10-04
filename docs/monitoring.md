# Monitoring des exécutions

Le pipeline conserve deux niveaux de suivi dans le schéma PostgreSQL `control` :

- `control.pipeline_runs` contient le statut et les volumes globaux d'un run ;
- `control.pipeline_step_runs` détaille chaque étape avec son statut, sa durée,
  son volume traité et son éventuelle erreur.

## Étapes suivies

Une exécution complète enregistre sept étapes, dans cet ordre :

1. `staging_sessions`
2. `staging_pageviews`
3. `staging_products`
4. `staging_orders`
5. `staging_order_items`
6. `staging_refunds`
7. `warehouse_et_marts`

Une étape passe de `STARTED` à `SUCCESS` ou `FAILED`. En cas d'échec, le
message d'erreur est conservé et l'exécution globale est également marquée
`FAILED`.

## Consulter le dernier run

```sql
SELECT
    run_id,
    pipeline_name,
    started_at,
    finished_at,
    status,
    rows_extracted,
    rows_loaded,
    rows_rejected,
    error_message
FROM control.pipeline_runs
ORDER BY started_at DESC
LIMIT 1;
```

## Examiner ses étapes

```sql
SELECT
    step_name,
    status,
    duration_seconds,
    rows_processed,
    error_message
FROM control.pipeline_step_runs
WHERE run_id = '<run_id>'
ORDER BY step_run_id;
```

Le fichier `logs/pipeline.log` affiche également un résumé technique en fin
d'exécution. Il permet de repérer rapidement l'étape défaillante ou anormalement
lente sans commencer par interroger PostgreSQL.
