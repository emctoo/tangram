from __future__ import annotations

import logging
import threading
import time

from traffic.core.traffic import Traffic
from traffic.data import ModeS_Decoder

import numpy as np
import pandas as pd

from .modes_decoder_client import Decoder


def crit(df):
    return (
        df.vertical_rate_barometric_std - df.vertical_rate_inertial_std
    ).abs()


def threshold(df: pd.DataFrame):
    t = np.mean(df.criterion) + ADSBClient.multiplier * np.std(df.criterion)
    if t > ADSBClient.min_threshold:
        return t
    else:
        return ADSBClient.min_threshold


def turbulence(df: pd.DataFrame):
    return df.criterion > df.threshold


def anomaly(df):
    lat_1 = df.latitude > (np.mean(df.latitude) + 3 * np.std(df.latitude))
    lat_2 = df.latitude < (np.mean(df.latitude) - 3 * np.std(df.latitude))
    lon_3 = df.longitude > (np.mean(df.longitude) + 3 * np.std(df.longitude))
    lon_4 = df.longitude < (np.mean(df.longitude) - 3 * np.std(df.longitude))
    return lat_1 | lat_2 | lon_3 | lon_4


class ADSBClient:
    min_threshold : float = 150
    multiplier :  float = 1.2

    def __init__(self) -> None:
        self.running: bool = False
        self.decoder: Decoder = Decoder()
        self._pro_data: Traffic = None
        self._traffic: Traffic = None
        self.thread: threading.Thread = None

    @property
    def pro_data(self) -> Traffic:
        return self._pro_data

    @property
    def traffic(self) -> Traffic:
        return self._traffic

    @property
    def traffic_decoder(self) -> Traffic | None:
        df = pd.DataFrame.from_dict(
            self.decoder.traffic_records()["cumul"],
            orient="columns"
        )
        if df.empty:
            return None
        df["timestamp"] = pd.to_datetime(df.timestamp, unit="ms", utc=True)
        return Traffic(df)

    def resample_traffic(self, traffic: Traffic) -> Traffic:
        return (traffic.longer_than("1T")
                .resample(
                    "1s",
                    how={
                        "interpolate": set(traffic.data.columns).union(
                            {"track_unwrapped", "heading_unwrapped"}
                        )
                        - {"vertical_rate_barometric", "vertical_rate_inertial"}
                    },
                ).eval(max_workers=4))

    def calculate_traffic(self):
        traffic: Traffic = self.traffic_decoder
        if traffic is None:
            self._traffic = None
            return
        self._traffic = self.resample_traffic(traffic)

    def set_min_threshold(self, value: float):
        ADSBClient.min_threshold = value

    def set_multiplier(self, value: float):
        ADSBClient.multiplier = value

    def get_min_threshold(self) -> float:
        return ADSBClient.min_threshold

    def get_multiplier(self) -> float:
        return ADSBClient.multiplier

    def turbulence(self):
        if self._traffic is not None:
            try:
                self._pro_data = (
                    self._traffic.longer_than("1T")
                    .filter(
                        strategy=None,
                        # median filters for abnormal points
                        vertical_rate_barometric=3,
                        vertical_rate_inertial=3,  # kernel sizes
                    )
                    .agg_time(
                        # aggregate data over intervals of one minute
                        "1 min",
                        # compute the std of the data
                        vertical_rate_inertial="std",
                        vertical_rate_barometric="std",
                        # reduce one minute to one point
                        latitude="mean",
                        longitude="mean",
                    )
                    .assign(
                        # we define a criterion based on the
                        # difference between two standard deviations
                        # on windows of one minute
                        criterion=crit
                    )
                    .assign(
                        # we define a thushold based on the
                        # mean criterion + 1.2 * standar deviation criterion
                        threshold=threshold
                    )
                    .assign(turbulence=turbulence)
                    .assign(anomaly=anomaly)
                    .eval(max_workers=4)
                    .query("not anomaly")
                )
            except Exception as e:
                logging.warning(e)
        else:
            self._pro_data = None

    def calculate_live_turbulence(self):
        while self.running:
            self.calculate_traffic()
            self.turbulence()
            time.sleep(1)

    def start_live(self):
        self.running = True
        self.thread = threading.Thread(
            target=self.calculate_live_turbulence,
            daemon=True,
        )
        self.thread.start()

    def start_from_file(self, file: str, reference: str):
        self.clear()
        if file.endswith(".csv"):
            file_decoder = ModeS_Decoder.from_file(
                file, template="time,df,icao,shortmsg", reference=reference
            )
            self._traffic = self.resample_traffic(file_decoder.traffic)
            self.turbulence()
        elif file.endswith(".pkl") or file.endswith(".parquet"):
            self._traffic = Traffic.from_file(file)
            self._pro_data = self._traffic

    def start_from_database(self, data):
        self.clear()
        df = pd.concat(
            [
                pd.DataFrame.from_records(f["traj"]).assign(
                    callsign=f["callsign"]
                )
                for f in data
            ]
        )
        df["timestamp"] = pd.to_datetime(df.timestamp, utc=True)
        self._traffic = self.resample_traffic(Traffic(df))
        self.turbulence()

    def stop(self):
        self.running = False
        self.thread.join()

    def clear(self):
        self._traffic = None
        self._pro_data = None
