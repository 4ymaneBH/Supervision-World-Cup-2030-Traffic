"""Dash operations view with a Mapbox 3D H3 density layer."""

from __future__ import annotations

from datetime import datetime, timezone

from worldcup.analytics import cell_geojson, forecast_next_counts, hotel_view, latest_rows, next_alert, recommend_shuttle
from worldcup.config import ROOT, Settings
from worldcup.redis_store import recent_aggregates, recent_hotels
from worldcup.reference import cities_by_name, load_reference


def build_view(client, reference: dict, city: str, previous_alerts: dict, settings: Settings) -> dict:
    cells = [row for row in recent_aggregates(client, "cell") if row["city"] == city]
    venues = [row for row in recent_aggregates(client, "venue") if row["city"] == city]
    hotels = [row for row in recent_hotels(client) if row["city"] == city]
    current_venues = latest_rows(venues, ("city", "venue", "source"))
    alerts = []
    recommendations = []
    forecasts = {}
    state = dict(previous_alerts or {})
    city_reference = cities_by_name(reference)[city]
    seen = set()
    for row in current_venues:
        source = row["source"]
        identity = f"{city}:{row['venue']}:{source}"
        seen.add(identity)
        pressure = row.get("pressure")
        was_active = bool(state.get(identity))
        active = next_alert(was_active, pressure, settings.alert_high, settings.alert_low)
        state[identity] = active
        forecasts[source] = forecast_next_counts(item for item in venues if item["source"] == source and item["venue"] == row["venue"])
        if active:
            alerts.append(row)
            route = recommend_shuttle(city_reference, pressure, settings.alert_low if was_active else settings.alert_high)
            if route and not recommendations:
                recommendations.append(route)
    for identity in list(state):
        if identity.startswith(f"{city}:") and identity not in seen:
            state.pop(identity)
    latest_update = max((row["updated_at"] for row in [*cells, *venues, *hotels]), default=None)
    return {
        "geojson": cell_geojson(cells),
        "venues": current_venues,
        "hotels": hotel_view(hotels),
        "alerts": alerts,
        "recommendations": recommendations,
        "forecasts": forecasts,
        "alert_state": state,
        "latest_update": latest_update,
        "center": city_reference["center"],
    }


def create_app(settings: Settings | None = None):
    import redis
    from dash import Dash, Input, Output, State, ClientsideFunction, dcc, html
    from flask import jsonify

    settings = settings or Settings.from_env()
    reference = load_reference(settings.reference_path)
    city_names = list(cities_by_name(reference))
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    app = Dash(
        __name__,
        assets_folder=str(ROOT / "assets"),
        external_scripts=["https://api.mapbox.com/mapbox-gl-js/v3.33.0/mapbox-gl.js"],
        external_stylesheets=["https://api.mapbox.com/mapbox-gl-js/v3.33.0/mapbox-gl.css"],
        title="World Cup 2030 | Traffic Control",
    )

    @app.server.route("/health")
    def health():
        try:
            client.ping()
            return jsonify({"status": "ok", "redis": "ok"})
        except redis.RedisError:
            return jsonify({"status": "degraded", "redis": "unavailable"}), 503

    app.layout = html.Main(
        [
            dcc.Store(id="mapbox-token", data=settings.mapbox_access_token),
            dcc.Store(id="map-data"),
            dcc.Store(id="alert-state", data={}),
            dcc.Interval(id="refresh", interval=10_000, n_intervals=0),
            html.Header(
                [
                    html.Div("WORLD CUP 2030 / MAROC", className="eyebrow"),
                    html.H1("Transport & Spectateurs"),
                    html.P("Supervision des accès, des transports et des capacités hôtelières.", className="subtitle"),
                ],
                className="page-header",
            ),
            html.Div(
                [
                    html.Label("Ville", htmlFor="city"),
                    dcc.Dropdown(id="city", options=[{"label": city, "value": city} for city in city_names], value=city_names[0], clearable=False),
                    html.Div(id="freshness", className="freshness", role="status"),
                ],
                className="controls",
            ),
            html.Section(id="metrics", className="metrics", **{"aria-label": "Indicateurs"}),
            html.Section(
                [
                    html.Div(id="map", className="map-canvas", role="img", **{"aria-label": "Carte 3D des cellules H3"}),
                    html.Div(id="map-render-status", className="map-status", role="status"),
                ],
                className="map-panel",
                **{"aria-label": "Carte de densité"},
            ),
            html.Div(
                [
                    html.Section([html.H2("Alertes"), html.Div(id="alerts")], className="panel"),
                    html.Section([html.H2("Navettes suggérées"), html.Div(id="recommendations")], className="panel"),
                    html.Section([html.H2("Hôtels"), html.Div(id="hotels")], className="panel"),
                ],
                className="detail-grid",
            ),
            html.Footer("Données de démonstration synthétiques. Les suggestions ne commandent aucune flotte réelle."),
        ],
        className="shell",
    )

    @app.callback(
        Output("map-data", "data"),
        Output("metrics", "children"),
        Output("freshness", "children"),
        Output("alerts", "children"),
        Output("recommendations", "children"),
        Output("hotels", "children"),
        Output("alert-state", "data"),
        Input("refresh", "n_intervals"),
        Input("city", "value"),
        State("alert-state", "data"),
    )
    def refresh(_interval, city, alert_state):
        empty = {"geojson": {"type": "FeatureCollection", "features": []}, "center": cities_by_name(reference)[city]["center"]}
        try:
            view = build_view(client, reference, city, alert_state or {}, settings)
        except redis.RedisError:
            return empty, [], "Redis indisponible", html.P("Données temporairement indisponibles."), [], [], alert_state or {}

        by_source = {row["source"]: row for row in view["venues"]}
        cards = []
        for source, label in (("stadium_access", "Accès stade"), ("transit_validation", "Transport")):
            row = by_source.get(source)
            count = row["event_count"] if row else None
            pressure = row.get("pressure") if row else None
            cards.append(
                html.Article(
                    [
                        html.Div(label, className="metric-label"),
                        html.Div(f"{count:,}" if count is not None else "—", className="metric-value"),
                        html.Div(f"Pression {pressure:.0%}" if pressure is not None else "Capacité inconnue", className="metric-note"),
                        html.Div(
                            f"Prévision : {view['forecasts'][source]:,}" if view["forecasts"].get(source) is not None else "Prévision indisponible",
                            className="metric-note",
                        ),
                    ],
                    className="metric-card",
                )
            )
        hotel = next((item for item in view["hotels"] if item["area_id"] == "citywide"), None)
        cards.append(
            html.Article(
                [
                    html.Div("Occupation hôtelière", className="metric-label"),
                    html.Div(f"{hotel['occupancy']:.0%}" if hotel and not hotel["stale"] else "—", className="metric-value"),
                    html.Div("Données périmées" if hotel and hotel["stale"] else "Données disponibles" if hotel else "Source indisponible", className="metric-note"),
                ],
                className="metric-card",
            )
        )
        alert_cards = [
            html.Article(f"{row['source']} · {row['venue']} · pression {row['pressure']:.0%}", className="list-item alert")
            for row in view["alerts"]
        ] or [html.P("Aucune alerte active.", className="muted")]
        route_cards = [
            html.Article(
                [html.Strong(route["route"]), html.Span(f"{route['available_seats']} places · {route['travel_minutes']} min"), html.Small(route["reason"])],
                className="list-item",
            )
            for route in view["recommendations"]
        ] or [html.P("Aucune suggestion en cours.", className="muted")]
        hotel_cards = [
            html.Article(
                f"{item['area_id']} · {item['rooms_occupied']:,}/{item['rooms_available'] + item['rooms_occupied']:,} chambres · "
                + ("périmé" if item["stale"] else "à jour"),
                className="list-item",
            )
            for item in view["hotels"]
        ] or [html.P("Aucune donnée hôtelière.", className="muted")]
        updated = view["latest_update"]
        freshness = f"Dernière mise à jour : {updated}" if updated else "En attente d'événements"
        return {"geojson": view["geojson"], "center": view["center"]}, cards, freshness, alert_cards, route_cards, hotel_cards, view["alert_state"]

    app.clientside_callback(
        ClientsideFunction(namespace="worldcup", function_name="renderMap"),
        Output("map-render-status", "children"),
        Input("map-data", "data"),
        State("mapbox-token", "data"),
    )
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8050, debug=False)
