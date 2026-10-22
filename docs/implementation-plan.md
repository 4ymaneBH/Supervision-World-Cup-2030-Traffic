# Plan d'implémentation

Ce plan couvre les quatre livrables du [mini-projet](<../Mini-Projet 15 - Coupe du Monde 2030 Transport & Spectateurs.pdf>). Il suit le [contrat et l'architecture proposés](architecture.md). **Statut : non démarré** ; les cases décrivent du travail à réaliser, pas du travail déjà livré.

## Principes de réalisation

- Obtenir d'abord un trajet complet avec des données synthétiques, puis ajouter les calculs et les sources réelles.
- Garder les seuils, la résolution H3, les capacités, les adresses des services et les secrets dans une configuration explicite.
- Accompagner chaque incrément de tests ciblés et d'un commit Git ; documenter les changements de contrat.
- Distinguer les objectifs du cahier des charges des hypothèses de conception et des résultats effectivement mesurés.

## Étapes et critères de fin

### 0. Environnement et données de référence

- [ ] Définir les versions compatibles de Python, Kafka, Spark/PySpark, H3, Redis, Dash et Mapbox, puis figer les dépendances.
- [ ] Ajouter une procédure de démarrage local reproductible, les fichiers de configuration d'exemple et une commande de vérification des services.
- [ ] Constituer un petit référentiel de villes, stades, gares, lignes, matchs et capacités synthétiques, avec provenance et unités.
- [ ] Trancher les décisions ouvertes de l'[architecture](architecture.md#6-confidentialité-et-décisions-ouvertes), en particulier la source hôtelière et les règles de déviation.

**Terminé lorsque :** un nouveau poste peut démarrer les services et exécuter un contrôle de santé, sans secret versionné.

### 1. Producteur d'événements — `worldcup_event_producer.py`

- [ ] Définir et valider les schémas versionnés pour `stadium-access` et `transit-validations` ; ajouter `event_id` pour la reprise et la déduplication.
- [ ] Générer des trajectoires synthétiques cohérentes avec les horaires des matchs, plusieurs villes et des pics paramétrables ; utiliser une graine pour reproduire les essais.
- [ ] Régler le débit, la durée, le nombre de producteurs et la proportion de messages invalides ; journaliser les compteurs émis et refusés.
- [ ] Publier sur Kafka avec gestion des erreurs et arrêt propre.

**Terminé lorsque :** des tests de schéma passent et que les deux topics reçoivent un nombre vérifiable d'événements au débit demandé sur une courte exécution.

### 2. Traitement streaming — `spark_worldcup_traffic.py`

- [ ] Lire les deux topics ; valider, normaliser et isoler les messages invalides avec une raison de rejet.
- [ ] Utiliser le temps événementiel, gérer les retards et dédupliquer `event_id` après redémarrage.
- [ ] Calculer les cellules H3, les fenêtres de densité par ville/lieu/cellule et les indicateurs de qualité ; rendre la résolution configurable.
- [ ] Joindre les capacités connues, calculer la pression seulement lorsqu'une capacité fiable est disponible et émettre les alertes.
- [ ] Configurer checkpoints, métriques de micro-lots et reprise ; publier les agrégats de façon idempotente vers Redis.

**Terminé lorsque :** un jeu connu, comprenant doublons, événements tardifs, coordonnées invalides et capacité absente, donne les agrégats attendus avant et après redémarrage.

### 3. Capacités hôtelières et prévision

- [ ] Définir un adaptateur pour des instantanés agrégés d'occupation/capacité hôtelière ; fournir un simulateur si aucune source autorisée n'est disponible.
- [ ] Calculer la tension hôtelière et afficher « données indisponibles » lorsque la source est absente ou périmée.
- [ ] Construire une prévision de référence à court terme à partir des fenêtres observées et du calendrier des matchs.
- [ ] Évaluer cette prévision sur des scénarios retenus à l'avance (pics, retards, absence de données) avant de proposer un modèle d'IA plus complexe.

**Terminé lorsque :** les valeurs hôtelières sont traçables à leur source et que l'erreur de prévision est publiée avec le jeu et la méthode d'évaluation.

### 4. Interface — `app_worldcup_control.py`

- [ ] Lire les agrégats Redis et afficher la dernière heure de mise à jour, les valeurs manquantes et les erreurs de source.
- [ ] Réaliser la heatmap H3 3D Mapbox avec filtres ville, match et temps ; ajouter les séries transport/stade/hôtel.
- [ ] Afficher les alertes et les recommandations de navettes avec leur motif, leur capacité de référence et leur état.
- [ ] Vérifier l'interface sur un scénario complet, y compris le départ ou la panne d'un composant.

**Terminé lorsque :** un événement émis apparaît au bon endroit et dans la bonne fenêtre, les alertes sont compréhensibles et une donnée périmée ne ressemble pas à une donnée actuelle.

### 5. Réorientation des navettes

- [ ] Définir les itinéraires candidats, leur capacité disponible et une règle de classement vérifiable.
- [ ] Publier automatiquement une recommandation lorsqu'une zone dépasse le seuil configuré, avec hystérésis et retour à l'état normal.
- [ ] Conserver une trace de la recommandation, des entrées utilisées et d'une éventuelle validation opérateur.
- [ ] Définir séparément une intégration de commande de flotte si un opérateur et une interface réelle sont fournis.

**Terminé lorsque :** des scénarios de congestion et de retour à la normale produisent des recommandations stables, reproductibles et justifiées.

### 6. Charge, optimisation et rapport — `load_testing_report.pdf`

- [ ] Définir l'environnement d'essai : machines, CPU/RAM, réseau, partitions Kafka, configuration Spark, H3, Redis et version du code.
- [ ] Exécuter une montée progressive (par exemple 1k, 10k, 25k puis 50k événements/s), avec échauffement et paliers documentés ; proposer un palier soutenu de 15 minutes à 50k/s.
- [ ] Mesurer simultanément événements produits, acceptés, rejetés et agrégés ; retard Kafka, temps Spark, latence événement→Redis→écran, CPU/RAM, erreurs et pertes.
- [ ] Tester les pics, le retard d'événements et le redémarrage d'un traitement ; régler partitions, parallélisme et écriture Redis si les métriques révèlent un goulot.
- [ ] Rédiger le PDF avec protocole, graphiques, résultats bruts, limites, réglages, débit soutenu maximal et conclusion explicite sur l'atteinte ou non de 50k/s.

**Terminé lorsque :** un autre lecteur peut reproduire le test et distinguer le débit annoncé du débit réellement traité, avec la latence et les pertes correspondantes. Le seuil de latence acceptable doit être convenu avant le test ; aucun résultat de performance n'est présumé.

## Ordre de dépendance

```text
0 Environnement + référentiels
  └─> 1 Producteur ─> 2 Streaming ─> 4 Interface ─> 5 Navettes
                           └───────> 3 Hôtel + prévision ──┘
                                      6 Charge et rapport : après le trajet complet
```

Une première démonstration de bout en bout est possible après les étapes 0, 1, 2 et une version minimale de 4. Les étapes 3 et 5 complètent les objectifs métier. Le test de charge final se fait sur la version intégrée, après les corrections révélées par les essais intermédiaires.

## Validation transversale

| Niveau | Vérification attendue |
| --- | --- |
| Contrat | Schémas valides/invalides, versions, coordonnées, fuseaux horaires et champs absents. |
| Calcul | Cellule H3 connue, fenêtres, doublons, événements tardifs, agrégats et états de capacité inconnue. |
| Intégration | Kafka → Spark → Redis → Dash, reprise après panne et absence d'agrégats en double. |
| Métier | Congestion simulée, seuil/hystérésis, prévision évaluée, recommandation explicable. |
| Performance | Débit durable, latence, pertes, saturation de chaque composant et reproductibilité du protocole. |

## Décisions à confirmer avant les derniers incréments

1. Qui fournit les capacités des stades, trains, bus/navettes et hôtels, avec quelle fraîcheur et quels droits d'usage ?
2. Quelles villes, rencontres, zones et résolutions H3 servent de référence à la démonstration ?
3. Qui valide les seuils d'alerte et les recommandations ; une commande de flotte réelle est-elle attendue ?
4. Quel environnement et quelle latence de bout en bout constituent les critères d'acceptation du test à 50 000 événements/s ?
5. Quelle conservation est permise pour les événements bruts contenant un identifiant de spectateur ?
