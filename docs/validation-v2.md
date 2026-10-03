# Validation technique de la V2

## Objectif

Cette validation confirme le fonctionnement du pipeline avec les sources réelles
et vérifie son comportement lors de deux exécutions consécutives. Le résultat
attendu est de ne pas dupliquer les commandes déjà chargées.

Date de validation : 2 octobre 2026.

## Sources vérifiées

| Source | Mode d'extraction | Volume |
|---|---|---:|
| Sessions web | CSV | 472 871 |
| Pages consultées | CSV par lots | 1 188 124 |
| Produits | JSON | 4 |
| Commandes | API REST incrémentale | 32 313 |
| Articles commandés | PostgreSQL | 40 025 |
| Remboursements | PostgreSQL | 1 731 |

## Première exécution

Identifiant : `0dffd462-ab57-4816-b537-2efcba43b227`

| Indicateur | Résultat |
|---|---:|
| Statut | SUCCESS |
| Lignes extraites | 1 735 068 |
| Lignes chargées | 1 735 068 |
| Lignes rejetées | 0 |
| Commandes présentes en staging | 32 313 |

Le checkpoint des commandes a été positionné sur :

- `last_created_at` : `2015-03-19 05:38:31` ;
- `last_id` : `32313`.

## Deuxième exécution

Identifiant : `dd1f0451-ac6e-4126-8e33-2c9c7ede1eba`

| Indicateur | Résultat |
|---|---:|
| Statut | SUCCESS |
| Lignes extraites | 1 702 755 |
| Lignes chargées | 1 702 755 |
| Lignes rejetées | 0 |
| Nouvelles commandes extraites | 0 |
| Commandes présentes en staging | 32 313 |

La différence de 32 313 lignes entre les deux exécutions correspond exactement
aux commandes déjà traitées. Les autres sources de la V2 restent chargées en
mode complet ou par lots.

## Volumes finaux dans le staging

| Table | Nombre de lignes |
|---|---:|
| `staging.website_sessions` | 472 871 |
| `staging.website_pageviews` | 1 188 124 |
| `staging.products` | 4 |
| `staging.orders` | 32 313 |
| `staging.order_items` | 40 025 |
| `staging.order_item_refunds` | 1 731 |

## Conclusion

La V2 satisfait les garanties vérifiées pendant cet essai :

- extraction incrémentale des commandes ;
- pagination de l'API ;
- conservation du checkpoint ;
- absence de duplication lors d'une deuxième exécution ;
- stabilité des volumes du staging ;
- traitement des pageviews par lots ;
- historique des exécutions au statut `SUCCESS` ;
- absence de lignes rejetées sur le jeu de données de référence.

Les tests automatisés couvrent en complément les retries, la reprise après
panne, les sources indisponibles et la quarantaine des lignes invalides.
