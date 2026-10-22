# Supervision World Cup 2030 Traffic

Plateforme de supervision en temps réel des déplacements de spectateurs pendant la Coupe du Monde 2030 au Maroc. Le projet vise à estimer la saturation des accès aux stades, des transports (dont Al Boraq et les réseaux urbains) et des capacités hôtelières, puis à présenter ces signaux sur une carte et à proposer des réorientations de navettes.

> **État du dépôt : cadrage.** Le PDF d'origine, cette documentation et le plan d'implémentation sont présents. Aucun pipeline, tableau de bord ou résultat de charge n'est encore implémenté.

## Cahier des charges

Le [mini-projet fourni](<Mini-Projet 15 - Coupe du Monde 2030 Transport & Spectateurs.pdf>) demande :

- l'ingestion des événements `stadium-access` et `transit-validations` via Kafka ;
- le traitement spatio-temporel avec Spark Structured Streaming et une grille H3 (S2 est également cité) ;
- la détection de goulots d'étranglement, le suivi des capacités hôtelières et la réorientation dynamique des navettes ;
- des agrégats disponibles rapidement dans Redis et une carte de chaleur 3D avec Dash et Mapbox ;
- un test de montée en charge jusqu'à **50 000 événements par seconde**.

Les quatre livrables explicitement demandés sont `worldcup_event_producer.py`, `spark_worldcup_traffic.py`, `app_worldcup_control.py` et `load_testing_report.pdf`.

## Parcours des données prévu

```text
Producteur / sources métier
    → Kafka (stadium-access, transit-validations, source hôtelière à définir)
    → Spark Structured Streaming (validation, temps événementiel, H3, agrégation)
    → Redis (état récent par cellule, ville, lieu et fenêtre)
    → Dash + Mapbox (carte 3D, alertes, recommandations de navettes)
```

Le schéma d'événement, les règles de calcul, les limites de confidentialité et les interfaces sont détaillés dans [l'architecture proposée](docs/architecture.md). Les étapes de réalisation, leurs critères de fin et les décisions à prendre sont dans le [plan d'implémentation](docs/implementation-plan.md).

## Périmètre du premier incrément

Une démonstration locale avec événements synthétiques : entrée au stade et validations de transport, densité H3 par fenêtre temporelle, agrégats Redis, carte mise à jour en continu, alertes de congestion et suggestion de navette. La tension hôtelière est prévue dans le modèle, sous réserve d'une source de capacité/occupation ; un simulateur peut servir à la démonstration.

La cible de 50 000 événements/s est **un objectif à mesurer**, pas une performance acquise. Le rapport final devra préciser le matériel, le protocole, le débit soutenu, la latence et les pertes éventuelles.

## Structure visée

```text
worldcup_event_producer.py     # événements synthétiques Kafka
spark_worldcup_traffic.py      # validation, H3, fenêtres et agrégats
app_worldcup_control.py        # supervision Dash / Mapbox
docs/architecture.md           # contrat et architecture proposés
docs/implementation-plan.md    # ordre de réalisation et validation
load_testing_report.pdf        # rapport à produire après les essais
```

Les fichiers Python et le rapport de charge ci-dessus sont des livrables **à créer** ; ils ne sont pas présents à ce stade.
