from __future__ import annotations
from enum import Enum
from threading import Thread, Event
import asyncio
from .client import HTTPClient, Request, Method
from websockets import client
import json
from .exceptions import ClosedSocketException

class Authenticate:
    VALUE = "Authenticate"

class GatewayEvent(Enum):
    Authenticate = Authenticate
    BeginTyping = "BeginTyping"
    EndTyping = "EndTyping"
    Ping = "Ping"
    Error = "Error"
    Authenticated = "Authenticated"
    Pong = "Pong"
    Ready = "Ready"
    Message = "Message"
    MessageUpdate = "MessageUpdate"
    MessageDelete = "MessageDelete"
    ChannelCreate = "ChannelCreate"
    ChannelUpdate = "ChannelUpdate"
    ChannelDelete = "ChannelDelete"
    ChannelGroupJoin = "ChannelGroupJoin"
    ChannelGroupLeave = "ChannelGroupLeave"
    ChannelStartTyping = "ChannelStartTyping"
    ChannelStopTyping = "ChannelStopTyping"
    ChannelAck = "ChannelAck"
    ServerUpdate = "ServerUpdate"
    ServerDelete = "ServerDelete"
    ServerMemberUpdate = "ServerMemberUpdate"
    ServerMemberJoin = "ServerMemberJoin"
    ServerMemberLeave = "ServerMemberLeave"
    ServerRoleUpdate = "ServerRoleUpdate"
    ServerRoleDelete = "ServerRoleDelete"
    UserUpdate = "UserUpdate"
    UserRelationship = "UserRelationship"

class GatewayKeepAlive(Thread):
    def __init__(self, *args, gateway: Gateway, interval: float, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.gateway: Gateway = gateway
        self.interval: float = interval
        self.daemon: bool = True
        self.stopEvent: Event = Event()

    def run(self) -> None:
        while not self.stopEvent.wait(self.interval):
            data: dict = self.GetPayload()
            coro = self.gateway.Send(data)
            func = asyncio.run_coroutine_threadsafe(coro, self.gateway.loop)
            func.result(10)

    def GetPayload(self) -> dict[str]:
        return {
            "type": GatewayEvent.Ping.value,
            "data": 0
        }

class Gateway:
    def __init__(self) -> None:
        self.client: HTTPClient = HTTPClient()
        self.loop = asyncio.get_event_loop()
        self.keepAlive: GatewayKeepAlive = GatewayKeepAlive(gateway=self, interval=20)
        self.websocket: client.WebSocketClientProtocol | None = client.WebSocketClientProtocol()

    async def Close(self) -> None:
        await self.client.Close()
        if self.websocket.open:
            await self.websocket.close()
            self.keepAlive.stopEvent.set()

    async def GetWebsocketURL(self) -> str:
        result: dict = await self.client.Request(Request(Method.GET, "/"))
        return result["ws"]

    async def Connect(self) -> None:
        if not self.websocket.open:
            self.websocket = await client.connect(await self.GetWebsocketURL())
            self.keepAlive.stopEvent.clear()
            self.keepAlive.start()

    async def Send(self, data: dict) -> None:
        if self.websocket.open:
            await self.websocket.send(json.dumps(data))
        else:
            raise ClosedSocketException()

    async def Receive(self) -> dict:
        if self.websocket.open:
            data: str = await self.websocket.recv()
            # match data["type"]:
            #     case GatewayEvent.Ready.value:

            # TODO: Dispatch events
            return json.loads(data)
        else:
            raise ClosedSocketException()

    async def Authenticate(self, token: str) -> None:
        await self.Send({
            "type": GatewayEvent.Authenticate.value.VALUE,
            "token": token
        })