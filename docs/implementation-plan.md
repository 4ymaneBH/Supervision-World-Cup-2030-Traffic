# Feuille de route technique

Cette feuille de route distingue les composants présents dans le [dépôt](../README.md) des validations qui nécessitent encore une infrastructure complète ou des sources de données autorisées.

## État actuel

| Lot | État | Preuve dans le dépôt |
| --- | --- | --- |
| Environnement local | Implémenté | `pyproject.toml`, `uv.lock`, `compose.yaml`, `.env.example`, `data/demo_reference.json` |
| Producteur synthétique | Implémenté | `worldcup_event_producer.py`, contrats et tests |
| Traitement streaming | Implémenté, intégration Kafka à vérifier | `spark_worldcup_traffic.py`, tests Spark de validation, tests Lua Redis |
| Hôtels et prévision simple | Implémenté avec données synthétiques | Instantanés synthétiques, fraîcheur et extrapolation de fenêtres |
| Tableau de bord et navettes | Implémenté avec données synthétiques | Dash, Mapbox H3, alertes avec hystérésis, route suggérée |
| Charge à 50 000/s | Non mesurée | Runner, PDF de précontrôle et protocole ; Kafka local indisponible |

## Étapes restantes, dans l'ordre

### Avancement Build Day : démo et première source

- [x] Pitch Three.js Rabat publié, avec scénario en trois étapes et données explicitement simulées.
- [x] Interface français/anglais, notes de présentation de 60 secondes et kit hors ligne téléchargeable.
- [x] Première capture du déploiement inspectée ; vérification DOM du scénario, de la traduction et du repli 2D. Le contrôle interactif du navigateur reste indisponible.
- [x] Adaptateur TomTom → stdout/Kafka `road-flow`, contrat routier séparé et tests sur fixture synthétique.
- [ ] Configurer `TOMTOM_API_KEY` localement et valider trois réponses réelles à Rabat.
- [ ] Ajouter la branche Spark des derniers instantanés routiers, l'état Redis et la couche de données réelles du tableau de bord.

Les [instructions de collecte routière](road-data.md) précisent les commandes et les limites. Le Site de pitch n'est pas connecté au collecteur ; ses gains de temps restent des hypothèses de scénario.

### 1. Vérifier le parcours complet

- [ ] Démarrer Kafka, Spark, Redis et Dash sur une machine Linux ou un environnement Spark compatible ; créer les quatre topics.
- [ ] Émettre un jeu contrôlé et confirmer les comptes, cellules H3, fenêtres, hôtels et alertes dans Redis et dans le navigateur.
- [ ] Réinjecter des doublons, des messages invalides et des événements retardés ; contrôler le topic `worldcup-invalid` et les agrégats.
- [ ] Redémarrer Spark avec le même checkpoint au milieu d'un micro-lot ; vérifier l'absence de double comptage et la reprise des trois requêtes.
- [ ] Documenter les versions, partitions Kafka, paramètres Spark et observations de cette intégration.

**Critère de fin :** les résultats de bout en bout sont reproductibles et l'interface n'affiche pas un état périmé comme actuel.

### 2. Compléter le scénario métier

- [ ] Ajouter un calendrier de matchs synthétique, un profil de pics et des filtres match/temps ; conserver les hypothèses séparées des données officielles.
- [ ] Remplacer les capacités synthétiques par des sources autorisées, datées et documentées ; tester l'absence de capacité.
- [ ] Évaluer la prévision simple sur des scénarios tenus à l'écart avant d'ajouter un modèle plus complexe.
- [ ] Définir un journal d'audit et la validation opérateur pour les suggestions de navettes. Une commande réelle de flotte exige un accord, une API et des contrôles d'accès distincts.
- [ ] Fixer la rétention des événements bruts et la pseudonymisation avec les responsables des données.

**Critère de fin :** chaque indicateur et recommandation affiche sa source, sa fraîcheur et son niveau de confiance documenté.

### 3. Mesurer et optimiser la charge

- [ ] Réserver un environnement de test avec CPU, RAM, réseau, partitions Kafka, Spark, Redis et `STREAM_ID` consignés.
- [ ] Lancer les paliers 1k, 10k, 25k et 50k événements/s, puis un palier de 15 minutes à 50k/s si l'environnement le permet.
- [ ] Mesurer, en plus des compteurs déjà disponibles, le retard Kafka, la durée des micro-lots, les pertes, la latence événement→Redis→écran et CPU/RAM.
- [ ] Tester retards d'événements, panne/reprise et pics ; régler partitions, parallélisme et écritures Redis selon les goulots observés.
- [ ] Régénérer `load_testing_report.pdf` depuis `artifacts/load-results.json` et les mesures complémentaires ; conclure explicitement sur la cible.

**Critère de fin :** un tiers peut reproduire les mesures et distinguer débit émis, traité pendant le palier et traité après vidange. Aucun succès à 50k/s n'est présumé.

## Validation déjà effectuée

- Les contrats du producteur, la génération reproductible, le rafraîchissement hôtelier et les règles analytiques passent leurs tests unitaires.
- Les tests Spark locaux vérifient les raisons de rejet, les colonnes publiées et la validation hôtelière. Le calcul H3 est également testé hors worker Python.
- Les scripts Lua Redis sont testés contre fakeredis : ajout idempotent, compteur de progression et refus d'un instantané hôtelier ancien.
- Le tableau de bord démarre et ses routes `/` et `/health` ont répondu sur cette machine ; un test Redis→vue couvre l'alerte, la navette, l'hôtel et le GeoJSON.
- Le précontrôle de charge a échoué sur la connexion à Kafka local. Le PDF enregistré ne contient donc aucun résultat de débit.

## Décisions métier ouvertes

1. Quelles villes, rencontres, capacités des sites/transports/hôtels et géométries sont autorisées pour un essai représentatif ?
2. Qui valide les seuils, la fraîcheur acceptable, l'erreur de prévision et les recommandations ?
3. Quel matériel et quels objectifs de latence accompagnent la cible de 50 000 événements/s ?
4. Quelle politique de conservation s'applique aux événements bruts avec identifiant de spectateur ?
