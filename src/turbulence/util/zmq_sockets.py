import logging
import os
import pickle
from typing import Any, Dict, Optional

import zmq
from requests import Session
from traffic.core import Traffic

import pandas as pd

os.environ["no_proxy"] = "localhost"
REQUEST_TIMEOUT = 5500

_log = logging.getLogger(__name__)


class DecoderSocket:
    def __init__(self, base_url: str = "tcp://127.0.0.1:5050") -> None:
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(base_url)
        self.base_url = base_url

    def traffic_records(
        self, start: pd.Timestamp = pd.Timestamp(0, tz="utc")
    ) -> Optional[Traffic]:
        request = {
            "origin": __name__,
            "timestamp": str(pd.Timestamp("now", tz="utc")),
            "payload": [str(start), "traffic"],
        }
        try:
            self.socket.send_json(request)
            if (self.socket.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                zobj = self.socket.recv()
                return pickle.loads(zobj)
        except zmq.ZMQError as e:
            _log.warning(str(__name__) + ": " + self.base_url + ":" + str(e))
            self.stop()
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REQ)
            self.socket.connect(self.base_url)
            return None

    def stop(self) -> None:
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()
        self.context.term()


class AggregatorSocket:
    def __init__(self, base_url: str = "http://localhost:5054") -> None:
        self.session = Session()
        self.base_url = base_url

    def icao24(
        self,
        icao24: str,
    ) -> Any:
        c = self.session.get(self.base_url, params={"icao": icao24})
        c.raise_for_status()

        return c.json()

    def get_planes(self) -> Any:
        c = self.session.get(self.base_url)
        c.raise_for_status()

        return c.json()

    def traffic_records(self) -> Dict[str, Any]:
        try:
            c = self.session.get(self.base_url + "/traffic")
            c.raise_for_status()
        except Exception as e:
            logging.warning("decoder" + str(e))
            return {"traffic": None}
        return c.json()
