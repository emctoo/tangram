#!/usr/bin/env python
#

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Callable, Set

import websockets

# log = logging.getLogger(__name__)
log = logging.getLogger("tangram")


class Channel:
    def __init__(self, connection: Jet1090WebsocketClient, channel: str, loop=None) -> None:
        self.connection = connection
        self.channel = channel
        self.loop = loop or asyncio.get_event_loop()
        self._event_handlers: dict[str, Set[Callable]] = {}
        self.join_ref = 0
        self.ref = 0

    def join(self) -> Channel:
        return self.send("phx_join", {})

    async def join_async(self) -> Channel:
        return await self.send_async("phx_join", {})

    async def on_join(self, join_ref, ref, channel, event, status, response) -> None:
        """default joining handler"""
        log.info("ignore joining reply: %s %s", status, response)

    async def run_event_handler(self, event: str, *args, **kwargs) -> None:
        """this is called from the connection when a message is received"""
        if event == "phx_reply":
            for fn in self._event_handlers.get("join", []):
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            else:
                await self.on_join(*args, **kwargs)
            return

        for fn in self._event_handlers.get(event, []):
            # print(fn)
            result = fn(*args, **kwargs)
            # print(result)
            if asyncio.iscoroutine(result):
                await result

    async def send_async(self, event: str, payload: dict) -> Channel:
        message = json.dumps(["0", "0", self.channel, event, payload])
        await self.connection.send(message)
        if event == "phx_join":
            self.join_ref += 1
        self.ref += 1
        return self

    def send(self, event: str, payload: dict) -> Channel:
        message = json.dumps(["0", "0", self.channel, event, payload])
        self.loop.run_until_complete(self.connection.send(message))
        if event == "phx_join":
            self.join_ref += 1
        self.ref += 1
        return self

    def on_event(self, event: str, fn: Callable) -> Channel:
        if event not in self._event_handlers:
            self._event_handlers[event] = set()
        self._event_handlers[event].add(fn)
        return self

    def off_event(self, event: str, fn: Callable) -> Channel:
        self._event_handlers[event].remove(fn)
        return self

    def on(self, event: str) -> Callable:
        def decorator(fn):
            self.on_event(event, fn)
            return fn

        return decorator

    def off(self, event: str) -> Callable:
        def decorator(fn):
            self.off_event(event, fn)

        return decorator


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            log.info("creating new instance of %s", cls.__name__)
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        # else:
        #     log.info('init with existing instance of %s', cls.__name__)
        #     cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]


class Jet1090WebsocketClient(metaclass=Singleton):
    # callbacks = {}  # f'{channel}-{event}' -> callback

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, loop=None):
        self.websocket_url: str
        self._CHANNEL_CALLBACKS = {}  # f'{channel}-{event}' -> callback
        self.channels = {}
        self.loop = loop or asyncio.get_running_loop()
        self.connected: bool = False

    def connect(self, websocket_url: str):
        """connect to the websocket server, regiter callbacks before calling this
        this is the entrypoint for the asyncio loop, most likely ran at the end of the code"""
        self.loop.run_until_complete(self.async_connect(websocket_url))

    async def async_connect(self, websocket_url: str):
        """asyncio context entrypoint
        this is started in a global startup hook."""
        self.websocket_url = websocket_url
        # ping/pong keepalive disabled
        # https://websockets.readthedocs.io/en/stable/topics/timeouts.html
        self._connection = await websockets.connect(self.websocket_url, ping_interval=None)
        log.info("connected to %s", self.websocket_url)

    def add_channel(self, channel_name: str) -> Channel:
        channel = Channel(self, channel_name, self.loop)
        self.channels[channel_name] = channel
        log.info("added a new channel %s %s", channel_name, channel)
        return channel

    async def send(self, message: str):
        await self._connection.send(message)

    def start(self) -> None:
        self.loop.run_until_complete(asyncio.gather(self._heartbeat(), self._dispatch()))

    async def start_async(self) -> None:
        log.info("starting jet1090 websocket client ...")
        await asyncio.gather(self._heartbeat(), self._dispatch())

    async def _heartbeat(self):
        """keepalive to the jet1090 server"""
        ref = 0
        while True:
            await self._connection.send(json.dumps(["0", str(ref), "phoenix", "heartbeat", {}]))
            log.debug("jet1090 keepalive message sent")

            await asyncio.sleep(60)
            ref += 1

    async def _dispatch(self):
        """dispatch messages to registered callbacks"""
        try:
            async for message in self._connection:
                # log.debug("message: %s", message)
                [join_ref, ref, channel, event, payload] = json.loads(message)
                status, response = payload["status"], payload["response"]
                ch: Channel | None = self.channels.get(channel)
                if not ch:
                    continue
                await ch.run_event_handler(event, join_ref, ref, channel, event, status, response)
        except websockets.exceptions.ConnectionClosedError:
            log.error("connection lost, reconnecting %s...", self.websocket_url)
            await self.async_connect(self.websocket_url)
            for ch in self.channels:
                await self.channels[ch].join_async()


jet1090_websocket_client: Jet1090WebsocketClient = Jet1090WebsocketClient()


# example


def on_joining_system(_join_ref, _ref, channel, event, status, response) -> None:  # noqa
    log.info("joined %s/%s, status: %s, response: %s", channel, event, status, response)


def on_heartbeat(join_ref, ref, channel, event, status, response) -> None:  # noqa
    log.info("heartbeat: %s", response)


def on_datetime(join_ref, ref, channel, event, status, response) -> None:  # noqa
    # log.info("datetime: %s", response)
    pass


def on_jet1090_message(join_ref, ref, channel, event, status, response) -> None:  # noqa
    skipped_fields = ["timestamp", "timesource", "system", "frame"]
    log.info("jet1090: %s", {k: v for k, v in response["timed_message"].items() if k not in skipped_fields})


def main(ws_url: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    jet1090_websocket_client = Jet1090WebsocketClient(ws_url, loop)
    jet1090_websocket_client.connect(ws_url)

    system_channel = jet1090_websocket_client.add_channel("system").on_event("datetime", on_datetime)
    system_channel.join()
    # client.add_channel("system").join()

    jet1090_channel = jet1090_websocket_client.add_channel("jet1090").on_event("data", on_jet1090_message)
    jet1090_channel.join()

    jet1090_websocket_client.start()


if __name__ == "__main__":
    default_websocket_url = "ws://127.0.0.1:8080/websocket"

    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--websocket-url", dest="websocket_url", type=str, default=default_websocket_url)
    parser.add_argument(
        "-l", "--log-level", dest="log_level", default="info", choices=["debug", "info", "warning", "error", "critical"]
    )
    args = parser.parse_args()
    log.setLevel(args.log_level.upper())

    try:
        main(args.websocket_url)
    except KeyboardInterrupt:
        print("\rbye.")
