# Analyses Python

La dernière couche du projet transforme les marts PostgreSQL en cinq analyses
reproductibles : ventes, clients, marketing, funnel et produits.

## Générer les résultats

Après avoir exécuté le pipeline et renseigné `.env` :

```bash
python -m src.analysis.report
```

Les résultats sont écrits dans `reports/analysis/`. Chaque thème produit un
fichier CSV réutilisable et un graphique PNG. Les CSV conservent les valeurs
exactes ; les graphiques facilitent la lecture des tendances et comparaisons.

## Sources analytiques

| Analyse | Mart source | Grain de sortie |
|---|---|---|
| Ventes | `marts.daily_performance` | mois |
| Clients | `marts.customer_summary` | statut client |
| Marketing | `marts.marketing_performance` | canal et campagne |
| Funnel | `marts.funnel_performance` | étape globale |
| Produits | `marts.product_performance` | produit |

Les taux mensuels et globaux sont recalculés à partir des volumes agrégés. Ils
ne sont pas obtenus en faisant la moyenne de pourcentages journaliers, ce qui
évite de donner le même poids à des journées de tailles différentes.
