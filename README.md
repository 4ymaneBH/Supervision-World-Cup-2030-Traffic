# Supervision World Cup 2030 Traffic

Démonstration locale de supervision des accès aux stades, validations de transport et capacités hôtelières. Le [mini-projet fourni](<Mini-Projet 15 - Coupe du Monde 2030 Transport & Spectateurs.pdf>) fixe les besoins ; [l'architecture](docs/architecture.md) décrit le contrat de données et les limites ; le [plan](docs/implementation-plan.md) suit les travaux restants.

## État actuel

Le producteur synthétique, le traitement Spark Structured Streaming, les agrégats Redis et le tableau de bord Dash/Mapbox sont implémentés. Les trois flux Kafka sont `stadium-access`, `transit-validations` et `hotel-occupancy`. Les messages invalides vont à `worldcup-invalid`. Les recommandations de navettes sont des **simulations**, sans commande de flotte.

La cible de **50 000 événements/s n'a pas été vérifiée**. Le [rapport de charge](load_testing_report.pdf), généré depuis le [résultat brut du précontrôle](docs/load-test-preflight.json), indique qu'aucun palier n'a pu être exécuté ici : le broker Kafka local était indisponible. Le script de mesure et le générateur du rapport sont prêts pour un environnement complet.

## Démarrage local

Prérequis : Python 3.10 à 3.13, [uv](https://docs.astral.sh/uv/), Java 17 ou 21 et Docker Compose. Un compte Mapbox avec un jeton public est nécessaire pour la carte 3D. Les services de démonstration ne doivent pas être exposés tels quels sur un réseau public.

Dans PowerShell, depuis la racine du dépôt :

```powershell
uv sync --extra test
docker compose up -d
uv run python scripts/create_topics.py
$env:MAPBOX_ACCESS_TOKEN = "votre-jeton-public"
$env:PYSPARK_SUBMIT_ARGS = "--packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1 pyspark-shell"
```

Puis, dans trois terminaux distincts ayant les mêmes variables d'environnement :

```powershell
uv run python spark_worldcup_traffic.py
uv run python app_worldcup_control.py
uv run python worldcup_event_producer.py --count 10000 --rate 500 --seed 2030
```

Ouvrir `http://127.0.0.1:8050/`. `http://127.0.0.1:8050/health` vérifie la connexion Redis. Le processus Spark doit démarrer **avant** le producteur lors du premier lancement, car son offset initial est `latest`. Pour un traitement ponctuel des offsets disponibles, utiliser `uv run python spark_worldcup_traffic.py --available-now` avec un checkpoint neuf. Les paramètres sont lus depuis l'environnement ; `.env.example` en donne la liste, mais le fichier `.env` n'est pas chargé automatiquement.

Sans Kafka, `uv run python worldcup_event_producer.py --sink stdout --count 5` permet d'inspecter les messages. Sans jeton Mapbox, le tableau de bord indique pourquoi la carte est absente ; les panneaux Redis restent utilisables. Les données de `data/demo_reference.json` sont inventées et ne représentent aucune capacité officielle de 2030.

## Tests et rapport de charge

```powershell
uv run --extra test python -m pytest -q
uv run python scripts/load_test.py --rates 1000 10000 25000 50000 --duration 60
uv run python scripts/render_load_report.py artifacts/load-results.json
```

Le test de charge exige un broker Kafka, Spark et Redis actifs, un `STREAM_ID` réservé à l'essai et aucun trafic concurrent. Le rapport lit uniquement les compteurs réellement produits par le script. Un essai soutenu de 15 minutes à 50 000/s se lance avec `--rates 50000 --duration 900`, sur une infrastructure dimensionnée à cet effet. Les compteurs actuels ne mesurent ni la latence par événement, ni les ressources système, ni le rendu navigateur. Ils ne suffisent donc pas à certifier la cible du brief.

## Fichiers principaux

| Chemin | Rôle |
| --- | --- |
| `worldcup_event_producer.py` | Génération et publication Kafka ou stdout ; rafraîchissement des instantanés hôteliers. |
| `spark_worldcup_traffic.py` | Validation, déduplication, H3, fenêtres glissantes et publication Redis. |
| `app_worldcup_control.py` | Carte H3 3D, indicateurs, alertes, hôtels et navettes suggérées. |
| `scripts/load_test.py` | Paliers de charge et compteurs observés dans `artifacts/load-results.json`. |
| `scripts/render_load_report.py` | PDF de mesures ou d'échec de précontrôle. |
| `docs/implementation-plan.md` | Travaux terminés, vérifications et étapes restantes. |

Les événements bruts comportent un `fan_id` synthétique. Le traitement ne publie pas ce champ dans Redis ou dans le tableau de bord. Une source réelle nécessiterait une revue des droits, de la rétention et de la pseudonymisation.
