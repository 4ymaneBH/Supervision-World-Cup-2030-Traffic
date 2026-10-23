window.dash_clientside = Object.assign({}, window.dash_clientside, {
  worldcup: {
    renderMap: function (payload, token) {
      if (!payload) return "En attente de données cartographiques.";
      if (!token) return "Définir MAPBOX_ACCESS_TOKEN pour afficher la carte 3D.";
      if (typeof mapboxgl === "undefined") return "Le script Mapbox n'a pas pu être chargé.";
      const empty = { type: "FeatureCollection", features: [] };
      const geojson = payload.geojson || empty;
      window.worldcupGeoJSON = geojson;
      const center = payload.center || [33.612, -7.135];
      if (!window.worldcupMap) {
        mapboxgl.accessToken = token;
        const map = new mapboxgl.Map({
          container: "map",
          style: "mapbox://styles/mapbox/dark-v11",
          center: [center[1], center[0]],
          zoom: 10,
          pitch: 55,
          bearing: -12,
          antialias: true
        });
        window.worldcupMap = map;
        map.addControl(new mapboxgl.NavigationControl(), "top-right");
        map.on("load", function () {
          map.addSource("crowd-h3", { type: "geojson", data: window.worldcupGeoJSON });
          map.addLayer({
            id: "crowd-extrusion",
            type: "fill-extrusion",
            source: "crowd-h3",
            paint: {
              "fill-extrusion-color": ["interpolate", ["linear"], ["get", "count"], 0, "#2ac0d1", 30, "#f3bc57", 100, "#ee694b"],
              "fill-extrusion-height": ["get", "height"],
              "fill-extrusion-base": 0,
              "fill-extrusion-opacity": 0.76
            }
          });
          map.on("click", "crowd-extrusion", function (event) {
            const feature = event.features && event.features[0];
            if (!feature) return;
            const point = event.lngLat;
            new mapboxgl.Popup().setLngLat(point)
              .setText(feature.properties.city + " · " + feature.properties.source + " · " + feature.properties.count + " événements")
              .addTo(map);
          });
        });
      } else {
        window.worldcupMap.setCenter([center[1], center[0]]);
        const source = window.worldcupMap.getSource("crowd-h3");
        if (source) source.setData(geojson);
      }
      return geojson.features.length + " cellules H3 affichées.";
    }
  }
});
