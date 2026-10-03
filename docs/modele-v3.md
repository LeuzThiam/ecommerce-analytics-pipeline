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

## Dimension client

`warehouse.dim_customer` contient une ligne par `user_id`. Dans les données
disponibles, cet identifiant représente un utilisateur web plutôt qu'un profil
nominatif : aucune information personnelle n'est inventée ou déduite.

La dimension expose :

- `customer_key`, la clé technique utilisée par les futures tables de faits ;
- `user_id`, la clé métier commune aux sessions et aux commandes ;
- les dates de première et dernière session ;
- la date de première commande, lorsqu'elle existe ;
- les indicateurs de session répétée et de statut acheteur.

Le chargement agrège les sessions et les commandes avant l'UPSERT. Une union
complète conserve aussi un éventuel acheteur absent de la source des sessions.
La première validation réelle recense 394 318 utilisateurs, dont 31 696
acheteurs.

## Dimension marketing

`warehouse.dim_marketing` contient une ligne par combinaison distincte de
source, campagne, contenu et référent HTTP. Sa clé technique `marketing_key`
sera portée par la future table `fact_sessions`.

Les champs UTM absents sont remplacés par un libellé « non renseigné » et le
référent absent par « aucun ». Cette normalisation permet de garantir l'unicité
de la combinaison malgré le comportement des valeurs `NULL` dans PostgreSQL.
L'indicateur `is_direct` identifie les sessions dont les trois attributs UTM et
le référent HTTP sont absents. Les sessions sans UTM mais provenant d'un moteur
de recherche restent ainsi distinguées du trafic réellement direct.

La première construction réelle produit 9 combinaisons marketing. Le trafic
sans UTM représente 83 328 sessions, dont 39 917 sessions réellement directes
sur les 472 871 sessions disponibles.

## Dimension appareil

`warehouse.dim_device` contient une ligne par type d'appareil observé dans les
sessions. Elle conserve le code métier `device_type`, lui associe un libellé
français et expose l'indicateur `is_mobile` pour simplifier les analyses.

La clé technique `device_key` sera portée par `fact_sessions`. Le chargement
par UPSERT garantit qu'un nouveau type pourra être ajouté sans recréer les
membres existants. La première construction produit deux lignes : `desktop`
pour 327 027 sessions et `mobile` pour 145 844 sessions.

## Tables de faits prévues

### Ventes

`fact_sales` utilisera l'article commandé comme grain. Cette granularité permet
d'analyser correctement les produits, les coûts, la marge et les remboursements
sans agréger prématurément les commandes contenant plusieurs articles.

La table relie chaque article aux dimensions date, produit et client. Les
identifiants de commande, de session et d'article restent disponibles comme
dimensions dégénérées pour les analyses détaillées.

Mesures stockées :

- prix de vente et coût de revient ;
- marge brute ;
- montant remboursé ;
- revenu net et profit net après remboursement ;
- indicateurs d'article principal et d'article remboursé.

Les remboursements sont agrégés par article avant le chargement afin de
préserver le grain même si plusieurs remboursements apparaissent ultérieurement.
La première réconciliation attend 40 025 articles et 1 731 articles remboursés.

### Sessions

`fact_sessions` utilisera la session web comme grain. Elle portera les métriques
de navigation et de conversion nécessaires aux analyses marketing et funnel.

Chaque session est reliée aux dimensions date, client, marketing et appareil.
Les pages vues et les commandes sont agrégées séparément avant les jointures
pour éviter de multiplier artificiellement les montants.

Mesures et attributs principaux :

- pages d'entrée et de sortie ;
- nombre de pages vues et durée de navigation ;
- indicateurs de répétition, rebond et conversion ;
- nombre de commandes et d'articles achetés ;
- chiffre d'affaires et marge brute de la session.

La première réconciliation attend 472 871 sessions, 211 640 rebonds et 32 313
sessions converties.

## Orchestration du warehouse

La construction du schéma en étoile est déclenchée automatiquement après le
chargement et la validation de toutes les sources du staging. L'ordre respecte
les dépendances de clés étrangères :

1. `dim_date` ;
2. `dim_product` ;
3. `dim_customer` ;
4. `dim_marketing` ;
5. `dim_device` ;
6. `fact_sales` ;
7. `fact_sessions`.

Une exécution n'est marquée `SUCCESS` dans `control.pipeline_runs` qu'après la
réussite du warehouse. Chaque table conserve sa propre transaction afin de ne
pas maintenir une transaction globale pendant les agrégations volumineuses.

## Réconciliation automatique

Après la construction des faits, neuf contrôles comparent le staging et le
warehouse : volumes des sessions, pages vues, commandes et articles, ventes et
marges des deux tables de faits, ainsi que les remboursements.

Les montants flottants du staging sont arrondis à deux décimales avant leur
comparaison avec les colonnes `NUMERIC` du warehouse. Le moindre écart lève une
erreur détaillant la mesure attendue et la valeur obtenue. Le pipeline ne peut
donc pas annoncer un succès avec un warehouse incomplet ou financièrement
incohérent.

## Mart de performance quotidienne

`marts.daily_performance` fournit une ligne par date de `dim_date`, prête à
être consommée par un tableau de bord. Elle combine sans double comptage :

- sessions, visiteurs, pages vues, rebonds et conversions ;
- commandes et articles achetés ;
- ventes, marge brute et valeur moyenne des commandes ;
- remboursements à leur date effective ;
- revenu net, profit net, taux de conversion et taux de rebond.

Les sessions, ventes et remboursements sont agrégés séparément avant leurs
jointures. Les jours sans activité sont conservés avec des mesures nulles, ce
qui facilite les séries temporelles continues.
