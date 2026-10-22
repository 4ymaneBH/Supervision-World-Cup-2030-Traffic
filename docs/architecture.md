# Architecture et contrat de données proposés

Ce document traduit le [cahier des charges](<../Mini-Projet 15 - Coupe du Monde 2030 Transport & Spectateurs.pdf>) en une architecture réalisable. Les choix chiffrés et les champs supplémentaires ci-dessous sont des **propositions de conception**, à valider lors du premier incrément. Ils ne sont pas présentés comme des exigences du PDF.

## 1. Capacités attendues et limites du brief

| Besoin du PDF | Traduction technique proposée |
| --- | --- |
| Flux d'accès aux stades et de validations de transport | Deux topics Kafka nommés `stadium-access` et `transit-validations`. |
| Découpage spatio-temporel H3 / S2 | H3 comme index principal ; résolution paramétrable et S2 reporté tant qu'aucun besoin de comparaison n'est établi. |
| Détection des goulots et réorientation de navettes | Calcul de pression par zone et publication de recommandations de déviation. |
| Tension des capacités hôtelières | Flux séparé de capacité/occupation, à obtenir ou à simuler ; les seuls passages aux portiques ne permettent pas de la déduire. |
| Prédiction de saturation | Prévision à court terme fondée d'abord sur les séries agrégées et le calendrier des matchs, puis comparaison avec un modèle plus élaboré si les données le justifient. |
| Carte 3D et accès rapide | Redis pour les derniers agrégats ; Dash/Mapbox pour la carte, les séries et les alertes. |
| 50 000 événements/s | Objectif de test de bout en bout, avec résultats mesurés sur un environnement décrit. |

## 2. Flux et responsabilités

```text
Simulateur de supporters ────────────┐
Sources transport / accès futures ────┼──> Kafka ──> Spark Structured Streaming
Flux capacité/occupation hôtelière ───┘                 │
                                                       ├─> rejets + métriques de qualité
                                                       └─> agrégats H3 / ville / lieu
                                                                  │
                                                                  v
                                                                Redis
                                                                  │
                                                                  v
                                                         Dash + Mapbox 3D
                                                                  │
                                                                  v
                                                  alertes et recommandations de navettes
```

- `worldcup_event_producer.py` émet des événements synthétiques reproductibles, dont des pics autour de matchs et des trajets par transport collectif. Il permet un débit contrôlable.
- `spark_worldcup_traffic.py` valide les messages, utilise le **temps de l'événement**, déduplique, calcule les cellules H3 et les fenêtres, puis publie des états agrégés dans Redis. Le stockage des événements rejetés et les checkpoints doivent être persistants.
- `app_worldcup_control.py` lit l'état agrégé, affiche la carte et les alertes, et expose la justification d'une recommandation. Le tableau de bord ne lit pas directement les identifiants des spectateurs.
- Le flux hôtelier transmet des instantanés d'occupation et de capacité par zone et heure. Son adaptateur réel, sa fréquence et ses droits d'accès restent à définir.

## 3. Contrat d'événement

Le PDF donne l'exemple d'un événement contenant `fan_id`, `city`, `venue`, `lat`, `lon`, `timestamp` et `action = gate_checkin`. Le producteur peut reprendre ces champs. Pour fiabiliser le traitement, le schéma normalisé ajoute `event_id`, `schema_version` et `source` ; `venue` peut être absent pour une validation de transport.

| Champ normalisé | Type | Règle initiale |
| --- | --- | --- |
| `event_id` | chaîne | Identifiant unique stable lors des reprises ; obligatoire. |
| `schema_version` | entier | Version du contrat ; commencer à `1`. |
| `source` | chaîne | `stadium_access` ou `transit_validation`. |
| `city` | chaîne | Ville hôte connue ; référentiel à définir. |
| `venue` | chaîne ou nul | Stade, gare ou arrêt si connu. |
| `lat`, `lon` | nombres | Coordonnées WGS84 valides ; rejeter les coordonnées hors limites. |
| `timestamp` | chaîne ISO 8601 | Horodatage UTC avec `Z` ; les événements trop tardifs sont comptés séparément. |
| `action` | chaîne | Valeur autorisée par la source, par exemple `gate_checkin`. |
| `fan_id` | chaîne ou nul | Champ du message source ; **non stocké dans Redis ni affiché**. À remplacer par un identifiant pseudonyme si une jointure est indispensable. |

Exemple proposé, compatible avec le format du PDF et enrichi pour la déduplication :

```json
{
  "event_id": "EVT-000001",
  "schema_version": 1,
  "source": "stadium_access",
  "fan_id": "FAN-88301",
  "city": "Casablanca",
  "venue": "Grand Stade de Benslimane",
  "lat": 33.612,
  "lon": -7.135,
  "timestamp": "2030-06-15T16:30:00Z",
  "action": "gate_checkin"
}
```

Le schéma hôtelier est distinct : `city`, `area_id`, `timestamp`, `rooms_available`, `rooms_occupied`, `source_id`. Il doit porter des **comptes agrégés**, pas des réservations individuelles. Les capacités des stades, lignes et navettes proviennent d'un référentiel versionné ; leur provenance doit être visible dans l'interface.

## 4. Calculs et état publié

1. **Validation.** Vérifier le schéma, les coordonnées, la ville, l'horodatage et les valeurs métier ; diriger les messages invalides vers un flux de rejet mesurable.
2. **Temps événementiel.** Dédupliquer par `event_id`, définir un retard maximal configurable et calculer des fenêtres glissantes. Valeurs de départ à tester : fenêtre d'une minute, pas de dix secondes et retard toléré de deux minutes.
3. **Index H3.** Calculer la cellule à une résolution configurable (résolution 8 comme point de départ à mesurer), puis agréger les comptes par cellule, source et fenêtre. Le choix doit être contrôlé visuellement près des stades et gares.
4. **Densité et pression.** La densité est un nombre d'événements par cellule/fenêtre. La saturation exige en plus une capacité de référence ; ne pas appeler « taux d'occupation » un simple nombre de passages. Calcul proposé : `pression = demande_estimee / capacité_disponible`, avec état « inconnu » si la capacité manque.
5. **Prévision.** Établir une référence simple (tendance récente + calendrier des matchs), comparer les prévisions à l'observé et n'afficher une confiance que si elle est mesurée. Une méthode d'IA plus complexe vient après constitution d'un jeu historique utilisable.
6. **Alertes et navettes.** Déclencher une alerte sur seuils configurables, avec hystérésis pour éviter les oscillations. Classer les itinéraires alternatifs selon leur capacité restante et leur temps estimé ; publier la recommandation et son motif. Une commande réelle aux opérateurs de flotte nécessite une interface et des règles d'autorisation qui ne figurent pas dans le brief.

L'état Redis doit contenir uniquement les agrégats récents et les métadonnées utiles à leur interprétation : `city`, `venue`, `h3_cell`, `window_start`, `window_end`, `event_count`, `capacity`, `pressure`, `quality_status`, `updated_at`. Prévoir des clés versionnées et une expiration configurable pour éviter les données périmées. Les clés exactes seront fixées avec le code et testées de bout en bout.

## 5. Interface et exploitation

L'écran principal présente une carte de chaleur H3 en 3D, un filtre ville/match/heure, les zones à risque, l'occupation hôtelière disponible et une liste de recommandations de navettes. Chaque valeur doit indiquer son heure de mise à jour ; une source absente ou obsolète doit apparaître comme telle. Le jeton et les droits Mapbox sont des paramètres de déploiement, jamais des valeurs enregistrées dans Git.

Mesures minimales : événements reçus/valides/rejetés par seconde, retard Kafka, durée des micro-lots Spark, latence événement→Redis→écran, nombre de clés actives et âge du dernier état. Les checkpoints, la reprise et l'écriture idempotente dans Redis doivent être vérifiés par un redémarrage contrôlé.

## 6. Confidentialité et décisions ouvertes

- Limiter les données individuelles dès l'ingestion ; agréger avant l'exposition au tableau de bord et définir la durée de conservation des flux bruts avec les responsables des données.
- Fixer avec les parties prenantes les sources réelles d'occupation hôtelière, de capacité des lignes et de flotte de navettes.
- Valider la liste des villes, stades, gares, matchs et les coordonnées de référence avant la démonstration.
- Confirmer les seuils d'alerte, les limites de latence, le niveau d'automatisation de la réorientation et l'environnement de test à 50 000 événements/s.
