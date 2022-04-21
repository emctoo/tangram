var live;
function getFlight_data(icao) {
  document.getElementById("icao").innerHTML = icao;
  url = "flight/" + icao
  $.getJSON(url, function (data) {
    flight_id = document.getElementById('flight_id');
    departure = document.getElementById('departure');
    destination = document.getElementById('destination');
    aircraft_id = document.getElementById('aircraft_id');

    if (data.flightId === undefined) {
      flight_id.innerHTML = ""; departure.innerHTML = ""; aircraft_id.innerHTML = ""; destination.innerHTML = "";
    } else {
      flight_id.innerHTML = data.flightId.id;
      departure.innerHTML = data.flightId.keys.aerodromeOfDeparture;
      destination.innerHTML = data.flightId.keys.aerodromeOfDestination;
      aircraft_id.innerHTML = data.flightId.keys.aircraftId;
    }
  });
  document.getElementById("flight").hidden = false;
}

function whenClicked(e) {
  var icao = (e.target.feature.properties.icao === undefined) ? (e.target.feature.geometry.properties.icao) : e.target.feature.properties.icao
  draw_chart(icao, live);
  getFlight_data(icao);
}
function onEachPlane(feature, layer) {
  var popupContent = "<p>ICAO: " + feature.properties.icao + "<br>Callsign: " + feature.properties.callsign + "</p>";
  layer.bindPopup(popupContent);
  layer.on({
    click: whenClicked,
  });
}
function onEachTurb(feature, layer) {
  var popupContent = "<p>ICAO: " + feature.properties.icao + "<br>Callsign: " + feature.properties.callsign + "</p>";
  layer.bindPopup(popupContent);
  layer.on({
    click: whenClicked,
  });
}

function onEachAirep(feature, layer) {
  var popupContent =
    "<p>Callsign: " +
    feature.properties.callsign +
    "<br>ICAO: " +
    feature.properties.icao24 +
    "<br>Typecode: " +
    feature.properties.typecode +
    "<br>From: " +
    feature.properties.created +
    "<br>To: " +
    feature.properties.expire +
    "<br>Phenomenon: " +
    feature.properties.phenomenon +
    "</p>";
  layer.bindPopup(popupContent);
}

function onEachSigmet(feature, layer) {
  var popupContent =
    "<p>id Sigmet: " +
    feature.properties.idSigmet +
    "<br>Hazard: " +
    feature.properties.hazard +
    "<br>From: " +
    feature.properties.validTimeFrom +
    "<br>To: " +
    feature.properties.validTimeTo +
    "</p>";
  layer.bindPopup(popupContent);
}

function onEachCat(feature, layer) {
  var popupContent =
    "<p>id Cat: " +
    feature.properties.identifier +
    "<br>Start: " +
    feature.properties.startValidity +
    "<br>End: " +
    feature.properties.endValidity +
    "<br>Intensity: " +
    feature.properties.intensity +
    "<br>Intensity value: " +
    feature.properties.intensityValue +
    "</p>";
  layer.bindPopup(popupContent);
}

function createCustomIcon(feature, latlng) {
  let myIcon = L.icon({
    iconUrl: "plane.png",
    iconSize: [30, 30], // width and height of the image in pixels
    iconAnchor: [12, 12], // point of the icon which will correspond to marker's location
    popupAnchor: [0, 0], // point from which the popup should open relative to the iconAnchor
  });
  return L.marker(latlng, {
    icon: myIcon,
    rotationAngle: feature.properties.dir,
  });
}

function loadTable(tableId, fields, data) {
  var rows = "";
  $.each(data, function (index, item) {
    var row = "<tr>";
    $.each(fields, function (index, field) {
      row += "<td>" + item["properties"][field + ""] + "</td>";
    });
    rows += row + "<tr>";
  });
  $("#" + tableId + " tbody").html(rows);
}
function updateTableSigmet(data) {
  loadTable(
    "table_sigmet",
    ["idSigmet", "hazard", "validTimeFrom", "validTimeTo", "firName"],
    data["features"]
  );
  document.getElementById("sigmet_count").innerHTML = Object.keys(
    data.features
  ).length;
}
function getSigmet(wef = null, und = null) {
  var url = "context/sigmet";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + '?' + searchParams;
  }
  var sigmet;
  $.getJSON(url, function (data) {
    if (data.features == undefined) {
      data["features"] = {}
    }
    sigmet = data
    updateTableSigmet(data)
    sigmets.clearLayers();
    L.geoJson(data, {
      style: function (feature) {
        var d = feature.properties.hazard;
        return d == "TS"
          ? { color: "red" }
          : d == "TURB"
            ? { color: "blue" }
            : d == "MTW"
              ? { color: "yellow" }
              : d == "ICE"
                ? { color: "gray" }
                : { color: "black" };
      },
      onEachFeature: onEachSigmet,
    }).addTo(sigmets);
  });
  return sigmet;
}
function updateTableAirep(data) {
  loadTable(
    "table_airep",
    [
      "callsign",
      "icao24",
      "typecode",
      "phenomenon",
      "altitude",
      "center",
      "created",
      "expire",
      "reported_time",
      "updated",
    ],
    data["features"]
  );
  document.getElementById("airep_count").innerHTML = Object.keys(
    data.features
  ).length;
}
function getAirep(wef = null, und = null) {
  url = "context/airep";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + '?' + searchParams;
  }
  var airep;
  $.getJSON(url, function (data) {
    if (data.features == undefined) {
      data["features"] = {}
    }
    updateTableAirep(data);
    airep = data
    aireps.clearLayers();
    L.geoJson(data, {
      onEachFeature: onEachAirep,
    }).addTo(aireps);
  });
  return airep
}
function getCat(wef = null, und = null) {
  url = "context/cat";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + '?' + searchParams;
  }
  var cat;
  $.getJSON(url, function (data) {
    cat_sev.clearLayers();
    cat_mod.clearLayers();
    if ($.isEmptyObject(data)) {
      return
    }
    cat = data;
    L.geoJson(data, {
      filter: function (feature) {
        return feature.properties.intensityValue == 2
      },
      style: function () {
        return { color: "red", opacity: 0 }
      },
      onEachFeature: onEachCat,
    }).addTo(cat_sev);
    L.geoJson(data, {
      filter: function (feature) {
        return feature.properties.intensityValue == 1
      },
      style: function () {
        return { color: "gray", opacity: 0 }
      },
      onEachFeature: onEachCat,
    }).addTo(cat_mod);
  });
  return cat;
}
function getPlanes(und = null, history = 0) {
  url = "planes.geojson"
  if (und !== null) {
    url = url + "/" + und
  }
  if (history) {
    const searchParams = new URLSearchParams({ history: history });
    url = url + '?' + searchParams
  }
  $.getJSON(url, function (data) {
    var avion = document.getElementById("plane_count");
    avion.innerHTML = data.count;

    planes.clearLayers();
    L.geoJson(data.geojson, myLayerOptions).addTo(planes);
  });
}
function getTurbulence(und = null, history = 0) {
  url = "turb.geojson"
  if (und !== null) {
    url = url + "/" + und
  }
  if (history) {
    const searchParams = new URLSearchParams({ history: history });
    url = url + '?' + searchParams
  }
  var turbu;
  $.getJSON(url, function (data) {
    turbu = data
    turbulences.clearLayers();
    L.geoJson(data.geojson, {
      onEachFeature: onEachTurb,
    }).addTo(turbulences);
  });
  return turbu;
}
function getheatmap(und = null, history = 0) {
  url = "heatmap.data"
  if (und !== null) {
    url = url + "/" + und
  }
  if (history) {
    const searchParams = new URLSearchParams({ history: history });
    url = url + '?' + searchParams
  }
  var heatm;
  $.getJSON(url, function (data) {
    heatm = data.data;
    heatmapLayer.clearLayers();
    L.heatLayer(data.data, { radius: 25 }).addTo(heatmapLayer);
  });
  return heatm;
}

// function highlightTrajectory(e) {
//   var layer = e.target;
//   layer.setStyle({
//     weight: 4,
//     opacity: 1,
//     color: "#dbff4d",
//   });
//   layer.bringToFront();
// }

// //reset the hightlighted states on mouseout
// function resetTrajectory(e) {
//   geojsonStates.resetStyle(e.target);
// }


// //add these events to the layer object
// function onEachTrajectory(feature, layer) {
//   layer.on({
//     click: highlightTrajectory,
//     mouseout: resetTrajectory,
//   });
// }

// function getTrajectory(icao) {
//   $.getJSON(url, function (data) {
//     traj.clearLayers();
//     L.geoJson(data, {
//       onEachFeature: onEachTrajectory,
//     }).addTo(traj);
//   });
// }