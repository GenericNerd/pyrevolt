from __future__ import annotations
from enum import Enum
import json
from .user import User
from ..client import HTTPClient, Request, Method

class ChannelType(Enum):
    SavedMessages = "SavedMessages"
    DirectMessage = "DirectMessage"
    Group = "Group"
    TextChannel = "TextChannel"
    VoiceChannel = "VoiceChannel"

class Channel:
    def __init__(self, channelID: str, type: ChannelType, **kwargs) -> None:
        self.channelID: str = channelID
        self.type: ChannelType = type
        self.session = kwargs.get("session")

    def __repr__(self) -> str:
        return f"<pyvolt.{self.type.value} id={self.channelID}>"

    @staticmethod
    async def FromJSON(jsonData: str|bytes, session) -> Channel:
        data: dict = json.loads(jsonData)
        kwargs: dict = {}
        kwargs["session"] = session
        channel: Channel = None
        match data["channel_type"]:
            case ChannelType.SavedMessages.value:
                user: User|None = session.users.get(data["user"])
                if user is None:
                    user = await User.FromID(data["user"], session.token)
                channel = SavedMessages(data["_id"], user)
            case ChannelType.DirectMessage.value:
                if data.get("last_message_id") is not None:
                    kwargs["lastMessageID"] = data["last_message_id"]
                recipients: dict[User] = []
                for userID in data["recipients"]:
                    user: User|None = session.users.get(userID)
                    if user is None:
                        user = await User.FromID(userID, session.token)
                    recipients.append(user)
                channel = DirectMessage(data["_id"], data["active"], recipients, **kwargs)
            case ChannelType.Group.value:
                if data.get("description") is not None:
                    kwargs["description"] = data["description"]
                if data.get("last_message_id") is not None:
                    kwargs["lastMessageID"] = data["last_message_id"]
                if data.get("permissions") is not None:
                    kwargs["permissions"] = data["permissions"]
                if data.get("nsfw") is not None:
                    kwargs["nsfw"] = data["nsfw"]
                recipients: dict[User] = []
                owner: User = None
                for userID in data["recipients"]:
                    user: User|None = session.users.get(userID)
                    if user is None:
                        user = await User.FromID(userID, session.token)
                    if user.userID == data["owner"]:
                        owner = user
                    recipients.append(user)
                channel = Group(data["_id"], data["name"], recipients, owner, **kwargs)
            case ChannelType.TextChannel.value:
                if data.get("description") is not None:
                    kwargs["description"] = data["description"]
                if data.get("default_permissions") is not None:
                    kwargs["defaultPermissions"] = data["defaultPermissions"]
                if data.get("nsfw") is not None:
                    kwargs["nsfw"] = data["nsfw"]
                if data.get("last_message_id") is not None:
                    kwargs["lastMessageID"] = data["last_message_id"]
                channel = TextChannel(data["_id"], data["server"], data["name"], **kwargs)
            case ChannelType.VoiceChannel.value:
                if data.get("description") is not None:
                    kwargs["description"] = data["description"]
                if data.get("default_permissions") is not None:
                    kwargs["defaultPermissions"] = data["defaultPermissions"]
                if data.get("nsfw") is not None:
                    kwargs["nsfw"] = data["nsfw"]
                channel = VoiceChannel(data["_id"], data["server"], data["name"], **kwargs)
        session.channels[channel.channelID] = channel
        return channel

    @staticmethod
    async def FromID(channelID: str, session) -> Channel:
        if session.channels.get(channelID) is not None:
            return session.channels[channelID]
        client: HTTPClient = HTTPClient()
        request: Request = Request(Method.GET, "/channels/" + channelID)
        request.AddAuthentication(session.token)
        result: dict = await client.Request(request)
        await client.Close()
        if result.get("type") is not None:
            return
        return await Channel.FromJSON(json.dumps(result), session)

    async def Send(self, content: str) -> None:
        client: HTTPClient = HTTPClient()
        request: Request = Request(Method.POST, f"/channels/{self.channelID}/messages", data = {"content": content})
        request.AddAuthentication(self.session.token)
        await client.Request(request)
        await client.Close()

class SavedMessages(Channel):
    def __init__(self, channelID: str, user: User, **kwargs) -> None:
        self.user: User = user
        super().__init__(channelID, ChannelType.SavedMessages, **kwargs)

class DirectMessage(Channel):
    def __init__(self, channelID: str, active: bool, recipients: dict[User], **kwargs) -> None:
        self.active: bool = active
        self.recipients: dict[User] = recipients
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        super().__init__(channelID, ChannelType.DirectMessage, **kwargs)

class Group(Channel):
    def __init__(self, channelID: str, name: str, recipients: dict[User], owner: User, **kwargs) -> None:
        self.name: str = name
        self.recipients: dict[User] = recipients
        self.owner: User = owner
        self.description: str|None = kwargs.get("description")
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        # TODO: Icon
        self.permissions: int|None = kwargs.get("permissions")
        self.nsfw: bool|None = kwargs.get("nsfw")
        super().__init__(channelID, ChannelType.Group, **kwargs)

class ServerChannel(Channel):
    def __init__(self, channelID: str, type: ChannelType, server, name: str, **kwargs) -> None:
        self.server = server
        self.name: str = name
        self.description: str | None = kwargs.get("description")
        # TODO: Icon
        self.defaultPermissions: int | None = kwargs.get("defaultPermissions")
        # TODO: Role permissions
        self.nsfw: bool | None = kwargs.get("nsfw")
        super().__init__(channelID, type, **kwargs)

class TextChannel(ServerChannel):
    def __init__(self, channelID: str, server, name: str, **kwargs) -> None:
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        super().__init__(channelID, ChannelType.TextChannel, server, name, **kwargs)

class VoiceChannel(ServerChannel):
    def __init__(self, channelID: str, server, name: str, **kwargs) -> None:
        super().__init__(channelID, ChannelType.VoiceChannel, server, name, **kwargs)