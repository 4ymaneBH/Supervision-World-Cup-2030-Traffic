# Première source routière à Rabat

Le producteur `worldcup_road_producer.py` constitue la prochaine étape du plan : collecter des observations routières et les publier dans le topic Kafka distinct `road-flow`. Il utilise uniquement la bibliothèque standard Python pour HTTP. Les dépendances Kafka existantes ne sont nécessaires qu'avec `--sink kafka`.

## Vérifier sans clé ni réseau

Depuis la racine du dépôt :

```powershell
uv run python worldcup_road_producer.py --fixture data/road_flow_fixture.json
```

Cette commande émet trois messages JSON avec `source_mode=simulated`. Le fixture est manuscrit ; ce ne sont pas des mesures TomTom enregistrées.

## Activer la collecte réelle

Configurer `TOMTOM_API_KEY` dans l'environnement local avant de démarrer le processus. Ne pas enregistrer la valeur dans Git ni dans les fichiers du Site. Comme dans le reste du projet, `.env` n'est pas chargé automatiquement.

```powershell
uv run python worldcup_road_producer.py --polls 1
```

Trois points approximatifs figurent dans `data/rabat_road_points.json`. L'API renvoie le segment couvert le plus proche, dont la géométrie doit être contrôlée avant usage. Les vitesses sont demandées en km/h, les temps sont en secondes. Une observation de segment ne constitue pas une estimation du trajet complet.

Pour Kafka :

```powershell
uv run python scripts/create_topics.py --with-roads
uv run python worldcup_road_producer.py --sink kafka --polls 0 --interval 120
```

À trois points par interrogation toutes les deux minutes, cette configuration effectue 2 160 requêtes par jour en continu. Vérifier le quota du compte avant un fonctionnement prolongé. Ctrl+C arrête la collecte. La commande lance une seule série de requêtes par défaut.

## Contrat et limites

- `source=road_flow`, `provider=tomtom` et `source_mode=live|simulated` indiquent la provenance. Les clés Kafka sont les identifiants des segments.
- `retrieved_at` est l'heure UTC de collecte. `provider_timestamp=null` signale que cet endpoint ne fournit pas l'heure d'observation du fournisseur ; aucune fraîcheur de mesure n'est inventée.
- Les champs comprennent vitesse actuelle, vitesse de référence, durées actuelle/de référence, confiance du fournisseur, fermeture et géométrie `[longitude, latitude]`.
- Les erreurs ne journalisent pas l'URL de requête, car elle contient la clé API.
- Le producteur existant et le contrat des validations voyageurs gardent leur rôle. Les instantanés routiers ne sont jamais comptés comme des passagers.
- Le traitement Spark actuel ne souscrit pas encore à `road-flow`. La prochaine extension est une branche conservant le dernier instantané par segment dans Redis, puis une couche dédiée du tableau de bord.
- Le pitch Sites reste une simulation autonome. Il ne lit pas encore ce topic et ne conserve aucune clé API.

## État de validation

Les tests couvrent la normalisation, les unités, les coordonnées, les rejets, les erreurs HTTP sans fuite de clé et l'émission du fixture. La collecte réelle et Kafka de bout en bout restent à valider avec une clé configurée et un broker disponible.

Référence officielle : [TomTom Flow Segment Data](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data).
