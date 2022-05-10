import json
from datetime import datetime
import logging
from typing import Any, Union

from flask import (
    Blueprint,
    Response,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_cors import CORS
from traffic.core import Traffic

import pandas as pd

from turbulences.client.ADSBClient import ADSBClient
from .forms import DatabaseForm, ThresholdForm

from .view_functions import geojson_traffic

base_bp = Blueprint("base", __name__)
CORS(base_bp)


@base_bp.route("/stop")
def stop_client():
    current_app.live_client.stop()
    return {}


@base_bp.route("/context/flight/<path:icao>")
def get_info_flight(icao):
    try:
        data = current_app.network.icao24(icao)
    except Exception:
        data = {}
    return data


@base_bp.app_template_filter("format_time")
def format_datetime(value, format="medium"):
    return f"{value:%Y-%m-%d %H:%M:%S}"


@base_bp.route("/uptime")
def get_uptime() -> dict[str, Any]:
    return {"uptime": (datetime.now() - current_app.start_time).total_seconds()}


@base_bp.route("/turb.geojson")
def turbulence() -> dict[str, Any]:
    client = current_app.live_client
    history = request.args.get("history", default=0, type=int)
    if history:
        client = current_app.history_client
    und = request.args.get("und", default=None)
    icao24 = request.args.get("icao24", default=None)
    callsign = request.args.get("callsign", default=None)
    pro_data = client.pro_data
    if icao24 not in (None, ''):
        pro_data = pro_data.query(f"icao24=='{str(icao24)}'")
    if callsign not in (None, ''):
        pro_data = pro_data.query(f"callsign=='{str(callsign)}'")
    features = []
    if pro_data is not None:
        if und not in (None, ''):
            und = int(und) / 1000
            t = pd.Timestamp(und, unit="s", tz="utc")
            pro_data = pro_data.query(f"timestamp<='{str(t)}'")
        turb: Traffic = pro_data.query("turbulence")
        if turb is not None:
            for flight in turb:
                if flight.shape is not None:
                    for segment in flight.split("1T"):
                        if segment is not None:
                            try:
                                x = segment.geojson()
                            except Exception as e:
                                logging.exception(
                                    str(flight.icao24) + ":" + str(e)
                                )
                                x = None
                            if x is not None:
                                x.update(
                                        {
                                            "properties": {
                                                "icao": flight.icao24,
                                                "callsign": flight.callsign,
                                                "typecode": flight.typecode,
                                                "start": segment.start.timestamp(),
                                                "validity": segment.data["expire_turb"].iloc[0]
                                            }
                                        }
                                    )
                                features.append(x)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    encapsulated_geojson = {
        "count": len(geojson["features"]),
        "geojson": geojson,
    }
    return encapsulated_geojson


@base_bp.route("/chart.data/<path:icao>")
def chart_data(icao) -> Union[str, dict]:
    client = current_app.live_client
    history = request.args.get("history", default=0, type=int)
    if history:
        client = current_app.history_client
    pro_data = client.pro_data
    if pro_data is None:
        return {}
    resultats = pro_data[icao].data
    resultats_turb = resultats.query("turbulence")
    turb = zip(
        resultats_turb.to_dict()["timestamp"].values(),
        resultats_turb.to_dict()["turbulence"].values(),
    )
    vsi = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["vertical_rate_inertial"].values(),
    )
    vsb = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["vertical_rate_barometric"].values(),
    )
    cri = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["criterion"].values(),
    )
    thr = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["threshold"].values(),
    )
    altitude = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["altitude"].values(),
    )
    vsi_std = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["vertical_rate_inertial_std"].values(),
    )
    vsb_std = zip(
        resultats.to_dict()["timestamp"].values(),
        resultats.to_dict()["vertical_rate_barometric_std"].values(),
    )
    data_turb = list(
        {"t": timestamp.timestamp() * 1000, "y": t} for timestamp, t in turb
    )
    data_vsi = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)} for timestamp, t in vsi
    )
    data_vsb = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)} for timestamp, t in vsb
    )
    data_criterion = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)} for timestamp, t in cri
    )
    data_threshold = list(
        {"t": timestamp.timestamp() * 1000, "y": t} for timestamp, t in thr
    )
    data_altitude = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)}
        for timestamp, t in altitude
    )
    data_vsi_std = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)}
        for timestamp, t in vsi_std
    )
    data_vsb_std = list(
        {"t": timestamp.timestamp() * 1000, "y": str(t)}
        for timestamp, t in vsb_std
    )
    return json.dumps(
        [
            data_turb,
            data_vsi,
            data_vsb,
            data_criterion,
            data_threshold,
            data_altitude,
            data_vsi_std,
            data_vsb_std
        ]
    )


@base_bp.route("/planes.geojson")
def fetch_planes_Geojson() -> dict:
    client = current_app.live_client
    history = request.args.get("history", default=0, type=int)
    und = request.args.get("und", default=None)
    icao24 = request.args.get("icao24", default=None)
    callsign = request.args.get("callsign", default=None)

    if history:
        client = current_app.history_client
    data = client.traffic

    if icao24 not in (None, ''):
        data = data.query(f"icao24=='{str(icao24)}'")
    if callsign not in (None, ''):
        data = data.query(f"callsign=='{str(callsign)}'")

    if und not in (None, ''):
        und = int(und) / 1000
        t = pd.Timestamp(und, unit="s", tz="utc")
        data = data.query(f"timestamp<='{str(t)}'")
    return geojson_traffic(data)


@base_bp.route("/plane.png")
def favicon() -> Response:
    return send_from_directory("./static", "plane.png")


@base_bp.route("/context/sigmet")
def fetch_sigmets() -> dict:
    wef = request.args.get("wef", default=None, type=int)
    und = request.args.get("und", default=None, type=int)
    t = pd.Timestamp("now", tz="utc")  # noqa: F841
    if wef is not None:
        wef = wef / 1000
    if und is not None:
        und = und / 1000
        t = pd.Timestamp(und, unit="s", tz="utc")  # noqa: F841
    res = current_app.sigmet.sigmets(wef, und, fir="^(L|E)")
    if res is not None:
        res = res.query("validTimeTo>@t")._to_geo()
    else:
        res = {}
    return res


@base_bp.route("/context/airep")
def airep_geojson() -> dict:
    wef = request.args.get("wef", default=None, type=int)
    und = request.args.get("und", default=None, type=int)
    condition = wef is None and und is None
    if not condition:
        wef = wef / 1000
        und = und / 1000
    data = current_app.airep.aireps(wef, und)
    if data is not None:
        if condition:
            t = pd.Timestamp("now", tz="utc")  # noqa: F841
            data = data.query("expire>@t")
        result = data._to_geo()
    else:
        result = {}
    return result


@base_bp.route("/context/cat")
def clear_air_turbulence() -> dict:
    wef = request.args.get("wef", default=None, type=int)
    und = request.args.get("und", default=None, type=int)
    t = pd.Timestamp("now", tz="utc")
    if wef is not None:
        wef = wef / 1000
    if und is not None:
        und = und / 1000
        t = pd.Timestamp(und, unit="s", tz="utc")  # noqa: F841
    res = current_app.cat.metsafe(
        "metgate:cat_mf_arpege01_europe",
        wef=wef,
        bounds="France métropolitaine",
    )
    if res is None:
        res = current_app.cat.metsafe(
            "metgate_archive:cat_mf_arpege01_europe",
            wef=wef,
            bounds="France métropolitaine",
        )
    if res is not None:
        res = res.query("endValidity>@t").query("startValidity<=@t")
    else:
        return {}
    return res._to_geo()


@base_bp.route("/fonts/<path:filename>")
def serve_fonts(filename) -> Response:
    return send_from_directory("fonts/", filename)


@base_bp.route("/static/<path:filename>")
def serve_static(filename):
    response = send_from_directory("static/", filename)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@base_bp.route("/", methods=["GET", "POST"])
def home_page() -> str:
    client = current_app.live_client
    history = request.args.get("history", default=0, type=int)
    if history:
        client: ADSBClient = current_app.history_client

    form_database = DatabaseForm()
    if form_database.validate_on_submit():
        return redirect(
            url_for(
                "history.database_request",
                min=(str(form_database.startdate.data) + " " +
                     str(form_database.starttime.data)),
                max=(str(form_database.enddate.data) + " " +
                     str(form_database.endtime.data)),
            )
        )

    form_threshold = ThresholdForm()
    if form_threshold.validate_on_submit():
        client.set_min_threshold(form_threshold.threshold.data)
        client.set_multiplier(form_threshold.multiplier.data)
        client.turbulence()
    else:
        form_threshold.threshold.data = client.get_min_threshold()
        form_threshold.multiplier.data = client.get_multiplier()
    if history:
        return render_template(
            "index.html",
            history=1,
            form_database=form_database,
            form_threshold=form_threshold
        )

    return render_template(
        "index.html",
        history=0,
        form_database=form_database,
        form_threshold=form_threshold,
        uptime=get_uptime()['uptime']
    )


@base_bp.route("/heatmap.data")
@base_bp.route("/heatmap.data/<path:und>")
def get_heatmap_data(und=None):
    client = current_app.live_client
    history = request.args.get("history", default=0, type=int)
    if history:
        client = current_app.history_client
    data = {}
    pro_data = client.pro_data
    if pro_data is not None:
        if und is not None:
            und = int(und) / 1000
            t = pd.Timestamp(und, unit="s", tz="utc")
            pro_data = pro_data.query(f"timestamp<='{str(t)}'")
        turb: Traffic = pro_data.query("turbulence")
        if turb is not None:
            # turb_agg = turb.agg_latlon(
            #     resolution=dict(latitude=5, longitude=5), criterion="max"
            # )
            turb = turb.data[["latitude", "longitude", "turbulence"]].dropna()
            data = [
                [i.latitude, i.longitude, 1 if i.turbulence else 0]
                for i in turb.itertuples()
            ]
    return {"data": data}


@base_bp.route("/trajectory/<path:icao>")
def get_traj(icao: str):
    client = current_app.live_client
    history = request.args.get("history", default=False)
    if history:
        client = current_app.history_client
    data = client.pro_data
    features = []
    if data is not None:
        flight = data[icao]
        if flight.shape is not None:
            try:
                x = flight.geojson()
                x.update(
                    {
                        "properties": {
                            "icao": flight.icao24,
                        }
                    }
                )
                features.append(x)
            except Exception as e:
                logging.exception(str(flight.icao24) + ":" + str(e))

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    return geojson
