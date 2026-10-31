# Rabat Flow

A small, presentation-ready Three.js mobility simulation for the Casablanca Codex Community Build Day. It runs independently of Kafka, Spark, Redis, Mapbox, and API keys.

## Run

From the repository root:

```powershell
python -m http.server 8080 --directory pitch/dist
```

Open http://localhost:8080. Use **Play the story** for the guided pitch, or trigger the disruption and apply the recommendation yourself. Space pauses movement; R resets; F opens fullscreen. All controls also have visible buttons.

French is the default. The **FR / EN** switch preserves the scenario and playback state. A saved choice is restored; `?lang=fr` or `?lang=en` explicitly selects the language when sharing the Site.

Open **Notes de présentation / Presenter notes** for a bilingual speaking guide. The **Download offline backup** link contains all assets and a Windows launcher. To regenerate it locally, run `python pitch/scripts/build_backup.py` from the repository root. Unzip it, launch `START-DEMO.cmd`, and open the printed loopback URL. Python 3 is required, internet access is not.

## Scope and data

- The city is an illustrative Rabat model with approximate landmark locations. It is not an operational routing map.
- Vehicles, demand, incidents, recommendations, and KPIs are simulated. No real operator feed or OpenAI inference is connected.
- The existing Python Kafka/Spark pipeline is the implementation foundation; the pipeline diagram in this demo describes that architecture, not a live connection.
- OpenAI Sans is loaded locally from OpenAI's public CDN. The palette is Build Day inspired; this independent project does not imply OpenAI endorsement.
- Three.js 0.170.0 and OrbitControls are vendored locally under the MIT license. All runtime assets are local for reliable presentations.

## Files

- `dist/index.html`: presentation and controls.
- `dist/styles.css`: responsive layout and design tokens.
- `dist/scene.js`: Three.js Rabat scene and vehicle motion.
- `dist/simulation.js`: deterministic scenario state.
- `dist/app.js`: UI and guided pitch.
- `dist/i18n.js`: French/English interface, map labels and speaking notes.
- `scripts/build_backup.py`: reproducible offline presentation bundle.
- `.openai/hosting.json`: private Sites publication identity.

## Verification

Run `npm test` from `pitch/`. It generates the offline bundle and runs ten checks covering story timing, pause/speed, reset and reduced motion, input validation, scenario data, translation coverage and local assets. A DOM smoke harness also exercised language changes during a running story, localized accessibility labels, saved language, speaking notes and the animated 2D fallback. The first deployment screenshot was inspected; direct browser automation remains unavailable.

## Pitch en français, 60 secondes

1. **0–15 secondes :** « En 2030, le trajet vers le stade fait partie du match. Rabat Flow réunit la route, le train, le tram et le bus dans une même vue. »
2. **15–30 secondes :** Déclencher l’affluence. « Un seul ralentissement peut perturber plusieurs modes de transport. »
3. **30–45 secondes :** Montrer l’accès ouest. « Nous relions une perturbation à une réponse explicable, avec les hypothèses visibles. »
4. **45–60 secondes :** « Voici la simulation. Les fondations Kafka et Spark sont déjà développées. Les données routières réelles et les flux autorisés des opérateurs sont la prochaine étape. »

## 60-second pitch

1. **0–15 seconds:** “In 2030, the journey to the stadium is part of the match. Rabat Flow brings road, rail, tram, and bus movement into one view.”
2. **15–30 seconds:** Trigger the match-day surge. “A single bottleneck can cascade across transport modes.”
3. **30–45 seconds:** Show the alternative corridor. “We connect the disruption to an explainable response, with the assumptions visible.”
4. **45–60 seconds:** Apply the scenario recommendation. “This is the demo. The Kafka and Spark foundation is already in our repository. Next, real road and operator feeds replace the simulated sources.”

Illustrative improvements compare predefined scenario states and are not measured traffic outcomes.
