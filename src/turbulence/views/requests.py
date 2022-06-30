from threading import Timer

from ..client.turbulence import TurbulenceClient
from ..util.geojson import geojson_traffic, geojson_turbulence


class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class RequestBuilder:
    def __init__(self, client: TurbulenceClient) -> None:
        self.client: TurbulenceClient = client
        self.planes_position: dict = {}
        self.turb_result: dict = {}
        self.planethread: RepeatTimer = RepeatTimer(5, self.plane_request)
        self.planethread.start()
        self.turbthread: RepeatTimer = RepeatTimer(5, self.turb_request)
        self.turbthread.start()

    def plane_request(self):
        self.planes_position = geojson_traffic(self.client.traffic)

    def turb_request(self):
        self.turb_result = geojson_turbulence(self.client.pro_data)
