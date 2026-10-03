# Modèle analytique de la V3

## Principes de grain

Le grain définit ce que représente exactement une ligne. Il est fixé avant la
création des tables afin d'éviter les doubles comptages dans les analyses.

| Table | Grain |
|---|---|
| `warehouse.dim_date` | Une ligne par jour calendaire |
| `warehouse.dim_product` | Une ligne par produit métier |
| `warehouse.dim_customer` | Une ligne par utilisateur |
| `warehouse.dim_marketing` | Une ligne par combinaison marketing distincte |
| `warehouse.dim_device` | Une ligne par type d'appareil |
| `warehouse.fact_sales` | Une ligne par article commandé |
| `warehouse.fact_sessions` | Une ligne par session web |

## Dimension date

`warehouse.dim_date` couvre toute la plage temporelle présente dans le staging.
Sa clé technique est un entier au format `YYYYMMDD`, ce qui rend les jointures et
les filtres temporels explicites.

Attributs principaux :

- date complète ;
- jour du mois ;
- numéro et nom du mois ;
- trimestre ;
- année ;
- numéro et nom du jour de la semaine ;
- indicateur de week-end.

La construction utilise un UPSERT PostgreSQL. Elle peut donc être exécutée
plusieurs fois et étendre automatiquement la dimension lorsque de nouvelles
dates apparaissent dans le staging.

La première construction réelle couvre la période du 19 mars 2012 au 1er avril
2015, soit 1 109 jours calendaires.

## Dimension produit

`warehouse.dim_product` contient une ligne par produit métier présent dans
`staging.products`. Elle sépare :

- `product_key`, la clé technique générée par le warehouse et destinée aux
  futures tables de faits ;
- `product_id`, la clé naturelle provenant du système source ;
- `product_name`, le libellé normalisé du catalogue ;
- `created_at`, la date et l'heure de création du produit.

La contrainte d'unicité sur `product_id` garantit le grain de la dimension.
Son chargement utilise un UPSERT : une nouvelle exécution met à jour les
attributs connus sans modifier la clé technique ni dupliquer le produit.

## Tables de faits prévues

### Ventes

`fact_sales` utilisera l'article commandé comme grain. Cette granularité permet
d'analyser correctement les produits, les coûts, la marge et les remboursements
sans agréger prématurément les commandes contenant plusieurs articles.

### Sessions

`fact_sessions` utilisera la session web comme grain. Elle portera les métriques
de navigation et de conversion nécessaires aux analyses marketing et funnel.
