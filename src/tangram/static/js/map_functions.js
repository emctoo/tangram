var chart_history;

// let prior_selected = null;
// var selected = null;

const selected_handler = {
  get(target, prop, receiver) {
    if (prop === 'icao24') {
      // console.log('access selected.icao24', target[prop]);
      return target[prop];
    }
    return Reflect.get(target, prop, receiver); // fallback
  },
  set(target, prop, value, _receiver) {
    if (prop === 'icao24') {
      let prior_value = target[prop];
      target['prior_icao24'] = prior_value;
      target['icao24'] = value;
      console.log(`selected icao24 updated, ${prior_value} => ${value}`);
      // prompt to channel event handler
      if (value !== null) {
        // publishEvent(streamingChannel, "select", { icao24: value });
        newChannelEventPush(streamingChannel, "select", { icao24: value })
          .receive("ok", (resp) => {
            trajectoryPlots = [];
            console.log(`(${streamingChannel.topic}) select => `, resp);
          })
        return true;
      }
    }
  }
}

var selected = new Proxy({ icao24: null, prior_icao24: null }, selected_handler);

let trajectoryPlots = []; // array of (latitude, longitude)
// channel name: channel:trajectory:${icao24}
let trajectoryChannel = null;
let trajectoryPloyline = null;

function joinTrajectoryChannel(channelName) {
  console.log(`joining trajectory channel ${channelName}`);

  trajectoryChannel = socket.channel(channelName, { token: 'okToJoin' }); // no joining token required

  trajectoryChannel.on('new-data', (data) => {
    traj.clearLayers();
    // let plots = data.map(({ latitude, longitude }) => [latitude, longitude]);
    // const { latitude, longitude } = data;
    // trajectoryPlots.push([latitude, longitude]);

    console.log(`${trajectoryChannel.topic}`, data.length);
    // trajectoryPlots = data.map(({ latitude, longitude }) => [latitude, longitude]);
    trajectoryPlots = data;
    // console.log(`trajectoryPlots`, trajectoryPlots.length);

    L
      .polyline(trajectoryPlots, { color: 'black', weight: 1, smoothFactor: 2 })
      .addTo(traj);
  });

  trajectoryChannel
    .join()
    .receive("ok", ({ messages }) => {
      trajectoryPlots = [];
      console.log(`(${channelName}) joined`, messages);
    })
    .receive("error", ({ reason }) =>
      console.log(`failed to join ${channelName}`, reason)
    )
    .receive("timeout", () => console.log(`timeout joining ${channelName}`));
}


function getFlight_data(icao24, callsign, tail, typecode) {
  document.getElementById("icao24").innerHTML = icao24;
  document.getElementById("typecode").innerHTML = typecode;
  document.getElementById("tail").innerHTML = tail;
  var aircraft_id = document.getElementById("aircraft_id");
  aircraft_id.innerHTML = callsign;
  url = "context/flight/" + icao24;
  $.getJSON(url, function (data) {
    flight_id = document.getElementById("flight_id");
    departure = document.getElementById("departure");
    destination = document.getElementById("destination");

    if (data.flightId === undefined) {
      flight_id.innerHTML = "";
      departure.innerHTML = "";
      destination.innerHTML = "";
    } else {
      flight_id.innerHTML = data.flightId.id;
      departure.innerHTML = data.flightId.keys.aerodromeOfDeparture;
      destination.innerHTML = data.flightId.keys.aerodromeOfDestination;
      aircraft_id.innerHTML = data.flightId.keys.aircraftId;
    }
  });
  document.getElementById("flight").hidden = false;
}

function deselect_planes() {
  console.log(`deselect plan ${selected.icao24}`, trajectoryChannel);
  if (trajectoryChannel !== null) {
    leaveTrajectoryChannel(`channel:trajectory:${selected.icao24}`)
  }

  document.getElementById("chart-pane").style.display = "none";
  traj.clearLayers();
  $(".aircraft_selected").toggleClass("aircraft_img", true);
  $(".aircraft_selected").toggleClass("aircraft_selected", false);
  $(".turb_selected").toggleClass("turb_path", true);
  $(".turb_selected").toggleClass("turb_selected", false);

  selected.icao24 = null;
}



function whenFeatureSelected(feat) {
  let icao24 = $("#icao24").text();
  switch (feat) {
    case "speed":
      draw_chart(icao24, ["groundspeed", "IAS", "TAS"]);
      break;
    case "vertical_rate":
      draw_chart(icao24, ["vrate_barometric", "vrate_inertial", "vertical_rate"]);
      break;
    case "track":
      draw_chart(icao24, ["track", "heading", "roll"]);
      break;
    case "altitude":
    default:
      draw_chart(icao24, ["altitude", "selected_altitude"]);
      break;
  }
}



function onEachTurb(feature, layer) {
  layer.on({ click: onPlaneClicked });
}

function onEachAirep(feature, layer) {
  var popupContent =
    "<p>callsign: " +
    feature.properties.callsign +
    "<br>icao24: " +
    feature.properties.icao24 +
    "<br>Typecode: " +
    feature.properties.typecode +
    "<br>From: " +
    feature.properties.created +
    "<br>To: " +
    feature.properties.expire +
    "<br>Phenomenon: " +
    feature.properties.phenomenon +
    "<br>Altitude: " +
    feature.properties.altitude +
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

function getSigmet(wef = null, und = null) {
  var url = "context/sigmet";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + "?" + searchParams;
  }
  var sigmet;
  $.getJSON(url, function (data) {
    if (data.features == undefined) {
      data["features"] = {};
    }
    document.getElementById("sigmet_count").innerHTML = Object.keys(
      data.features
    ).length;
    sigmet = data;
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
function getAirep(wef = null, und = null) {
  url = "context/airep";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + "?" + searchParams;
  }
  var airep;
  $.getJSON(url, function (data) {
    if (data.features == undefined) {
      data["features"] = {};
    }
    document.getElementById("airep_count").innerHTML = Object.keys(
      data.features
    ).length;
    airep = data;
    aireps.clearLayers();
    L.geoJson(data, {
      onEachFeature: onEachAirep,
    }).addTo(aireps);
  });
  return airep;
}
function getCat(wef = null, und = null) {
  url = "context/cat";
  if ((wef !== null) & (und !== null)) {
    const searchParams = new URLSearchParams({ wef: wef, und: und });
    url = url + "?" + searchParams;
  }
  var cat;
  $.getJSON(url, function (data) {
    cat_sev.clearLayers();
    cat_mod.clearLayers();
    if ($.isEmptyObject(data)) {
      return;
    }
    cat = data;
    L.geoJson(data, {
      filter: function (feature) {
        return feature.properties.intensityValue == 2;
      },
      style: function () {
        return { color: "red", opacity: 0 };
      },
      onEachFeature: onEachCat,
    }).addTo(cat_sev);
    L.geoJson(data, {
      filter: function (feature) {
        return feature.properties.intensityValue == 1;
      },
      style: function () {
        return { color: "gray", opacity: 0 };
      },
      onEachFeature: onEachCat,
    }).addTo(cat_mod);
  });
  return cat;
}
function getPlanes(und = "", history = 0, icao24 = "", callsign = "") {
  url = "planes.geojson";
  const searchParams = new URLSearchParams({
    history: history,
    und: und,
    icao24: icao24,
    callsign: callsign,
  });
  url = url + "?" + searchParams;

  $.getJSON(url, function (data) { });
}

function getTurbulence(und = "", history = 0, icao24 = "", callsign = "") {
  url = "turb.geojson";
  const searchParams = new URLSearchParams({
    history: history,
    und: und,
    icao24: icao24,
    callsign: callsign,
  });
  url = url + "?" + searchParams;

  var turbu;
  $.getJSON(url, function (data) {
    turbu = data;
    turbulences.clearLayers();
    var turb_geojson = L.geoJson(data.geojson, {
      onEachFeature: onEachTurb,
      style: function (feature) {
        var icao24 = feature.geometry.properties.icao24;
        var intensity = feature.geometry.properties.intensity;
        var color = function () {
          return intensity >= 200
            ? "#8400ff"
            : (intensity < 200) & (intensity > 100)
              ? "#ff9900"
              : "#0084ff";
        };
        if (icao24 === selected.icao24) {
          return { className: "turb_selected turb-" + icao24, color: color() };
        }
        return { className: "turb_path turb-" + icao24, color: color() };
      },
      // function (feature) {
      //   var icao = feature.properties.icao;
      //   return icao == selected.icao24
      //     ? { className: "turb_selected" }
      //     : {
      //       className: "turb_path"
      //     };
      // }
    }).addTo(turbulences);
    heatm = data.geojson.features;
    var values = [];
    var res = [];
    heatm.forEach(function (key) {
      for (var i = 0, l1 = key.coordinates.length; i < l1; i++) {
        key.coordinates[i][3] = key.properties.intensity;
        res.push(key.coordinates[i]);
      }
      // values.push(Object.values());
    });

    hexLayer.data(res);
    // turb_geojson.eachLayer(function (layer) {
    //   layer._path.id = 'turb-' + layer.feature.geometry.properties.icao;
    // });
  });
  return turbu;
}
function getheatmap(und = null, history = 0) {
  url = "heatmap.data";
  if (und !== null) {
    url = url + "/" + und;
  }
  if (history) {
    const searchParams = new URLSearchParams({ history: history });
    url = url + "?" + searchParams;
  }
  var heatm;
  $.getJSON(url, function (data) {
    heatm = data.data;
    hexLayer.data(heatm);
  });
  return heatm;
}

function getTimeString(isLocal) {
  var hours;
  var minutes;
  var date = new Date();

  if (isLocal) {
    hours = date.getHours();
    minutes = date.getMinutes();
  } else {
    hours = date.getUTCHours();
    minutes = date.getUTCMinutes();
  }

  if (hours < 10) {
    hours = "0" + hours;
  }

  if (minutes < 10) {
    minutes = "0" + minutes;
  }

  return hours + ":" + minutes;
}

/// get trajectory data and draw on the map
function getAndDrawTrajectory(icao, und = "", history = 0) {
  const params = new URLSearchParams({ history, und });
  let url = `plugins / trajectory / icao24 / ${icao} ? ${params}`;
  // url = url + "?" + searchParams;
  $.getJSON(url, function (data) {
    traj.clearLayers();
    trajectoryPlots = data.map(({ latitude, longitude }) => [latitude, longitude]);
    // console.log(arr);
    if (trajectoryPlots.length > 0) {
      var polyline = L.polyline(trajectoryPlots, { color: 'black', weight: 1, smoothFactor: 2 }).addTo(traj);
      // zoom in
      // map.fitBounds(polyline.getBounds(), { padding: [400, 0] });
    }
  });
}
