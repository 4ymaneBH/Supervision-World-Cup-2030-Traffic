# Architecture et contrat de données

Ce document décrit l'architecture actuelle du pipeline de supervision et son contrat de données. Les capacités, seuils, itinéraires et coordonnées du référentiel sont **synthétiques** ; ils ne constituent pas des données officielles d'exploitation. La [feuille de route](implementation-plan.md) suit les vérifications et fonctions restantes.

## 1. Capacités et décisions techniques

| Capacité | Implémentation et portée |
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

- `worldcup_event_producer.py` émet des événements synthétiques reproductibles de stade et de transport, des instantanés hôteliers renouvelés, à un débit contrôlable. Un profil de pics autour des matchs reste à ajouter.
- `spark_worldcup_traffic.py` valide les messages, utilise le **temps de l'événement**, déduplique, calcule les cellules H3 et les fenêtres, puis publie des états agrégés dans Redis. Les rejets sont publiés dans le topic `worldcup-invalid` ; les checkpoints sont écrits sous `SPARK_CHECKPOINT_ROOT` et doivent être conservés pour une reprise.
- `app_worldcup_control.py` lit l'état agrégé, affiche la carte et les alertes, et expose la justification d'une recommandation. Le tableau de bord ne lit pas directement les identifiants des spectateurs.
- Le flux hôtelier transmet des instantanés d'occupation et de capacité par zone et heure. Son adaptateur réel, sa fréquence et ses droits d'accès restent à définir.

## 3. Contrat d'événement

Les événements de foule portent `fan_id`, `city`, `venue`, `lat`, `lon`, `timestamp` et une action telle que `gate_checkin`. Le contrat versionné ajoute `event_id`, `schema_version` et `source` pour fiabiliser le traitement ; `venue` peut être absent pour une validation de transport.

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

Exemple d'événement compatible avec le contrat versionné :

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
5. **Prévision.** La version actuelle extrapole linéairement les deux ou trois dernières fenêtres de comptes. Elle n'utilise pas encore de calendrier de matchs et n'a pas été évaluée sur un jeu historique. Aucune confiance chiffrée n'est affichée.
6. **Alertes et navettes.** Déclencher une alerte sur seuils configurables, avec hystérésis pour éviter les oscillations. Classer les itinéraires alternatifs selon leur capacité restante et leur temps estimé ; publier la recommandation et son motif. Une commande réelle aux opérateurs de flotte nécessite une interface dédiée et des règles d'autorisation supplémentaires.

L'état Redis contient les agrégats récents et les métadonnées utiles à leur interprétation : `city`, `venue`, `h3_cell`, `window_start`, `window_end`, `event_count`, `capacity`, `pressure`, `quality_status`, `updated_at`. Les clés portent le préfixe `wc:v1`, les agrégats et les index expirent selon `REDIS_TTL_SECONDS`. Un marqueur par micro-lot et agrégat empêche le double ajout lors d'une reprise proche ; sa durée de rétention est bornée, donc une reprise très tardive doit être vérifiée séparément.

## 5. Interface et exploitation

L'écran principal présente une carte H3 en extrusion 3D, un filtre par ville, les zones à risque, l'occupation hôtelière disponible et une liste de recommandations de navettes. Les filtres match/heure et une série historique restent à réaliser. L'heure de dernière mise à jour et l'absence de données sont visibles ; les instantanés hôteliers vieux de plus de cinq minutes sont signalés comme périmés. Le jeton et les droits Mapbox sont des paramètres de déploiement, jamais des valeurs enregistrées dans Git.

Mesures actuelles : événements produits et compteur Redis après micro-lot, avec débit moyen pendant chaque palier. Les événements rejetés sont consultables dans Kafka. Le retard Kafka, la durée des micro-lots, la latence événement→Redis→écran et CPU/RAM sont encore à instrumenter. La reprise et l'écriture idempotente doivent être vérifiées par un redémarrage contrôlé sur un cluster complet.

## 6. Confidentialité et décisions ouvertes

- Limiter les données individuelles dès l'ingestion ; agréger avant l'exposition au tableau de bord et définir la durée de conservation des flux bruts avec les responsables des données.
- Fixer avec les parties prenantes les sources réelles d'occupation hôtelière, de capacité des lignes et de flotte de navettes.
- Valider la liste des villes, stades, gares, matchs et les coordonnées de référence avant toute utilisation opérationnelle.
- Confirmer les seuils d'alerte, les limites de latence, le niveau d'automatisation de la réorientation et l'environnement de test à 50 000 événements/s.
