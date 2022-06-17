from __future__ import annotations

import base64
import logging
import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import click
from flask import Flask, current_app
from traffic.data import ModeS_Decoder

import pandas as pd
from turbulence import config_decoder

if TYPE_CHECKING:
    from traffic.core.structure import Airport

expire_frequency = pd.Timedelta(
    config_decoder.get("parameters", "expire_frequency", fallback="1 minute")
)
expire_threshold = pd.Timedelta(
    config_decoder.get("parameters", "expire_threshold", fallback="1 minute")
)
columns = set(config_decoder.get("columns", "columns", fallback=[]))
columns = {
    'timestamp', 'icao24', 'altitude', 'heading',
    'vertical_rate_barometric', 'vertical_rate_inertial',
    'track', 'vertical_rate', 'latitude', 'longitude',
    'callsign', 'track_rate'
}


class TrafficDecoder(ModeS_Decoder):
    def __init__(
        self,
        reference: None | str | Airport | tuple[float, float] = None,
        expire_frequency: pd.Timedelta = expire_frequency,
        expire_threshold: pd.Timedelta = expire_threshold,
    ) -> None:
        super().__init__(
            reference,
            expire_frequency=expire_frequency,
            expire_threshold=expire_threshold,
        )
        self.pickled_traffic: str = None
        self.name: str = ""

    @ModeS_Decoder.on_timer("5s")
    def prepare_request(self) -> None:
        t = self.traffic
        if t is not None:
            t = t.drop(set(t.data.columns) - columns, axis=1)
            t = t.assign(antenna=self.name)
        self.pickled_traffic = base64.b64encode(pickle.dumps(t)).decode("utf-8")


app_host = config_decoder.get("application", "host", fallback="127.0.0.1")
app_port = int(config_decoder.get("application", "port", fallback=5050))


app = Flask(__name__)


@app.route("/")
def home() -> dict[str, int]:
    d = dict(current_app.decoder.acs)
    return dict((key, len(aircraft.cumul)) for (key, aircraft) in d.items())


@app.route("/traffic")
def get_all() -> dict[str, str]:
    return {"traffic": current_app.decoder.pickled_traffic}


@click.command()
@click.argument("source")
@click.option(
    "--host",
    "serve_host",
    show_default=True,
    default=app_host,
    help="host address where to serve decoded information",
)
@click.option(
    "--port",
    "serve_port",
    show_default=True,
    default=app_port,
    type=int,
    help="port to serve decoded information",
)
@click.option("-v", "--verbose", count=True, help="Verbosity level")
def main(
    source: str = "delft",
    decode_uncertainty: bool = False,
    verbose: int = 0,
    serve_host: str | None = "127.0.0.1",
    serve_port: int | None = 5050,
):

    logger = logging.getLogger()
    if verbose == 1:
        logger.setLevel(logging.INFO)
    elif verbose > 1:
        logger.setLevel(logging.DEBUG)
    host = config_decoder.get("decoders."+source, "host")
    port = config_decoder.get("decoders."+source, "port")
    time_fmt = config_decoder.get(
        "decoders."+source, "time_fmt", fallback="default"
    )
    protocol = config_decoder.get("decoders."+source, "socket")
    data_path = config_decoder.get(
        "decoders."+source, "file", fallback="~/ADSB_EHS_RAW_%Y%m%d.csv"
    )
    reference = config_decoder.get("decoders."+source, "reference")
    dump_file = Path(data_path).with_suffix(".csv").as_posix()
    app.decoder = TrafficDecoder.from_address(
        host=host,
        port=int(port),
        reference=reference,
        file_pattern=dump_file,
        uncertainty=decode_uncertainty,
        tcp=False if protocol == "UDP" else True,
        time_fmt=time_fmt,
    )
    app.decoder.name = source
    # return app
    from gevent.pywsgi import WSGIServer
    http_server = WSGIServer((serve_host, serve_port), app)
    http_server.serve_forever()


if __name__ == "__main__":
    main()
