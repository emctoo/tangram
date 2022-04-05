var planes = L.layerGroup();
var turbulences = L.layerGroup();
var sigmets = L.layerGroup();
var aireps = L.layerGroup();
var cat_mod = L.layerGroup();
var cat_sev = L.layerGroup();
var heatmapLayer = L.layerGroup();

var map = L.map("map", { layers: [planes, turbulences] }).setView([43.57155, 1.47165], 7);

var overlays = {
  Planes: planes,
  Turbulences: turbulences,
  Sigmets: sigmets,
  Airep: aireps,
  Cat_mod: cat_mod,
  Cat_sev: cat_sev,
  Heatmap: heatmapLayer,
};
let myLayerOptions = {
  onEachFeature: onEachPlane,
  pointToLayer: createCustomIcon,
};
getSigmet();
getAirep();
getCat();
setInterval(function () {
  getSigmet();
  getAirep();
}, 30000);
setInterval(function () {
  getCat();
}, 600000);

var baselayer = L.tileLayer(
  "http://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
  {
    attribution:
      '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>',
  }
);

L.control
  .liveupdate({
    update_map: function () {
      getPlanes();
      getTurbulence();
      getheatmap();
    },
    interval: 4000,
  })
  .addTo(map)
  .startUpdating();

L.control.scale().addTo(map);
L.control.layers(null, overlays).addTo(map);
map.addLayer(baselayer);

var UptimeSec = document.getElementById("seconds_uptime").textContent;
setInterval(function () {

  distance = UptimeSec++;
  var days = Math.floor(distance / (60 * 60 * 24));
  var hours = Math.floor((distance % (60 * 60 * 24)) / (60 * 60));
  var minutes = Math.floor((distance % (60 * 60)) / 60);
  var seconds = Math.floor((distance % 60));
  var d = days == 0 ? "" : days + "d ";
  var h = hours == 0 ? "" : hours + "h ";
  document.getElementById("uptime").innerHTML = d + h + minutes + "m " + seconds + "s ";
}, 1000);
