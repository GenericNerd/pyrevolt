from __future__ import annotations
from enum import Enum
import json
from ..exceptions import InvalidMessageException
from ..client import Method
from .user import User
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from ..session import Session
    from .server import Server

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
        self.session: Session|None = kwargs.get("session")

    async def update(self, updateData: dict, clear: list[str] = []) -> None:
        for key, value in updateData.items():
            setattr(self, key, value)
        for key in clear:
            setattr(self, key, None)

    @staticmethod
    async def FromJSON(jsonData: str|bytes, session: Session) -> Channel:
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
                recipients: list[User] = []
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
                recipients: list[User] = []
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
                    kwargs["defaultPermissions"] = data["default_permissions"]
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
    async def FromID(channelID: str, session: Session) -> Channel:
        if session.channels.get(channelID) is not None:
            return session.channels[channelID]
        result: dict = await session.Request(Method.GET, f"/channels/{channelID}")
        if result.get("type") is not None:
            return
        return await Channel.FromJSON(json.dumps(result), session)

    @staticmethod
    async def AttemptParse(content: str, session: Session) -> Channel|bool:
        if content.startswith("<#") and content.endswith(">"):
            channelID: str = content[2:content.find(">")]
            channel: Channel|None = session.channels.get(channelID)
            if channel is None:
                channel = await Channel.FromID(channelID, session)
            return channel
        return False

    async def Send(self, **kwargs) -> None:
        await Message.Create(self, **kwargs)

    async def Edit(self, **kwargs) -> None:
        data: dict = {}
        if kwargs.get("name") is not None:
            data["name"] = kwargs["name"]
        if kwargs.get("description") is not None:
            data["description"] = kwargs["description"]
        if kwargs.get("nsfw") is not None:
            data["nsfw"] = kwargs["nsfw"]
        if kwargs.get("remove") is not None:
            data["remove"] = kwargs["remove"]

        result: dict = await self.session.Request(Method.PATCH, f"/channels/{self.channelID}", data=data)
        if result.get("type") is None:
            await self.update(result, data["remove"])

    async def Close(self) -> None:
        await self.session.Request(Method.DELETE, f"/channels/{self.channelID}")
        self.session.channels.pop(self.channelID)

class SavedMessages(Channel):
    def __init__(self, channelID: str, user: User, **kwargs) -> None:
        self.user: User = user
        super().__init__(channelID, ChannelType.SavedMessages, **kwargs)

    def __repr__(self) -> str:
        return f"<pyrevolt.SavedMessage id={self.channelID} user={self.user}>"

    def copy(self) -> SavedMessages:
        return SavedMessages(self.channelID, self.user, session=self.session)

class DirectMessage(Channel):
    def __init__(self, channelID: str, active: bool, recipients: list[User], **kwargs) -> None:
        self.active: bool = active
        self.recipients: list[User] = recipients
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        super().__init__(channelID, ChannelType.DirectMessage, **kwargs)

    def __repr__(self) -> str:
        return f"<pyrevolt.DirectMessage id={self.channelID} active={self.active} recipients={self.recipients}>"

    def copy(self) -> DirectMessage:
        return DirectMessage(self.channelID, self.active, self.recipients, session=self.session)

class Group(Channel):
    def __init__(self, channelID: str, name: str, recipients: list[User], owner: User, **kwargs) -> None:
        self.name: str = name
        self.recipients: list[User] = recipients
        self.owner: User = owner
        self.description: str|None = kwargs.get("description")
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        # TODO: Icon
        self.permissions: int|None = kwargs.get("permissions")
        self.nsfw: bool|None = kwargs.get("nsfw")
        super().__init__(channelID, ChannelType.Group, **kwargs)

    def __repr__(self) -> str:
        return f"<pyrevolt.Group id={self.channelID} name={self.name} recipients={self.recipients} owner={self.owner}>"

    def __str__(self) -> str:
        return self.name

    def copy(self) -> Group:
        return Group(self.channelID, self.name, self.recipients, self.owner, session=self.session)

class ServerChannel(Channel):
    def __init__(self, channelID: str, type: ChannelType, server: Server, name: str, **kwargs) -> None:
        self.server: Server = server
        self.name: str = name
        self.description: str | None = kwargs.get("description")
        # TODO: Icon
        self.defaultPermissions: int | None = kwargs.get("defaultPermissions")
        # TODO: Role permissions
        self.nsfw: bool | None = kwargs.get("nsfw")
        super().__init__(channelID, type, **kwargs)

    def __str__(self) -> str:
        return self.name

class TextChannel(ServerChannel):
    def __init__(self, channelID: str, server: Server, name: str, **kwargs) -> None:
        self.lastMessageID: str|None = kwargs.get("lastMessageID")
        super().__init__(channelID, ChannelType.TextChannel, server, name, **kwargs)

    def __repr__(self) -> str:
        return f"<pyrevolt.TextChannel id={self.channelID} server={self.server.serverID} name={self.name}>"

    def copy(self) -> TextChannel:
        return TextChannel(self.channelID, self.server, self.name, session=self.session)

class VoiceChannel(ServerChannel):
    def __init__(self, channelID: str, server: Server, name: str, **kwargs) -> None:
        super().__init__(channelID, ChannelType.VoiceChannel, server, name, **kwargs)

    def copy(self) -> VoiceChannel:
        return VoiceChannel(self.channelID, self.server, self.name, session=self.session)

    def __repr__(self) -> str:
        return f"<pyrevolt.VoiceChannel id={self.channelID} server={self.server.serverID} name={self.name}>"


class EmbedType(Enum):
    Website = "Website"
    Image = "Image"
    Text = "Text"

class EmbedImageSize(Enum):
    Large = "Large"
    Preview = "Preview"

class Embed:
    def __init__(self, type: EmbedType | None, **kwargs):
        self.type: EmbedType = type
        match self.type:
            case EmbedType.Website:
                self.url: str | None = kwargs.get("url")
                self.specials: dict | None = kwargs.get("specials")
                self.title: str | None = kwargs.get("title")
                self.description: str | None = kwargs.get("description")
                self.siteName: str | None = kwargs.get("siteName")
                self.iconURL: str | None = kwargs.get("iconURL")
                self.colour: str | None = kwargs.get("colour")
            case EmbedType.Image:
                self.url: str = kwargs["url"]
                self.width: int = kwargs["width"]
                self.height: int = kwargs["height"]
                self.size: EmbedImageSize = kwargs["size"]
            case EmbedType.Text:
                self.iconURL: str | None = kwargs.get("iconURL")
                self.url: str | None = kwargs.get("url")
                self.title: str | None = kwargs.get("title")
                self.description: str | None = kwargs.get("description")
                self.colour: str | None = kwargs.get("colour")
            case None:
                return

    def __repr__(self) -> str:
        return f"<pyrevolt.Embed type={self.type}>"

    def toJSON(self) -> str:
        data: dict[str, Any] = self.__dict__
        data["type"] = None
        return json.dumps(data)

    @staticmethod
    async def FromJSON(jsonData: str | bytes) -> Embed:
        data: dict = json.loads(jsonData)
        kwargs: dict = {}
        match data["type"]:
            case EmbedType.Website.value:
                kwargs["url"] = data["url"]
                kwargs["specials"] = data["specials"]
                kwargs["title"] = data["title"]
                kwargs["description"] = data["description"]
                kwargs["siteName"] = data["site_name"]
                kwargs["iconURL"] = data["icon_url"]
                kwargs["colour"] = data["colour"]
            case EmbedType.Image.value:
                kwargs["url"] = data["url"]
                kwargs["width"] = data["width"]
                kwargs["height"] = data["height"]
                kwargs["size"] = EmbedImageSize(data["size"])
            case EmbedType.Text.value:
                kwargs["iconURL"] = data.get("icon_url")
                kwargs["url"] = data.get("url")
                kwargs["title"] = data.get("title")
                kwargs["description"] = data.get("description")
                kwargs["colour"] = data.get("colour")
        return Embed(EmbedType(data["type"]), **kwargs)

    @staticmethod
    def Create(**kwargs):
        return Embed(EmbedType.Text, **kwargs)

class Masquerade:
    def __init__(self, **kwargs):
        self.name: str | None = kwargs.get("name")
        self.avatar: str | None = kwargs.get("avatar")

    @staticmethod
    async def FromJSON(jsonData: str | bytes) -> Masquerade:
        data: dict = json.loads(jsonData)
        return Masquerade(name=data["name"], avatar=data["avatar"])

class Reply:
    def __init__(self, messageID: str, mention: bool):
        self.messageID: str = messageID
        self.mention: bool = mention

    @staticmethod
    async def FromJSON(jsonData: str | bytes, session: Session) -> Reply:
        data: dict = json.loads(jsonData)
        return Reply(data["id"], data["mention"])

class Message:
    def __init__(self, messageID: str, channel: Channel, author: User, **kwargs):
        self.messageID: int = messageID
        self.channel: Channel = channel
        self.author: User = author
        self.content: str | None = kwargs.get("content")
        self.nonce: str | None = kwargs.get("nonce")
        self.edited: str | None = kwargs.get("edited")
        self.embeds: list[Embed] | None = kwargs.get("embeds")
        self.mentions: list[User] | None = kwargs.get("mentions")
        # TODO: Fix replies
        self.replies: list[Message] | None = kwargs.get("replies")
        self.masquerade: Masquerade | None = kwargs.get("masquerade")
        self.session: Session | None = kwargs.get("session")

    def __repr__(self) -> str:
        return f"<pyrevolt.Message id={self.messageID} channel={self.channel} author={self.author}>"

    def copy(self) -> Message:
        kwargs: dict = {}
        kwargs["content"] = self.content
        kwargs["nonce"] = self.nonce
        kwargs["edited"] = self.edited
        kwargs["embeds"] = self.embeds
        kwargs["mentions"] = self.mentions
        kwargs["replies"] = self.replies
        kwargs["masquerade"] = self.masquerade
        return Message(self.messageID, self.channel, self.author, **kwargs)

    async def update(self, updatedData: dict) -> None:
        self.edited = updatedData.get("edited", self.edited)
        if updatedData.get("content") is not None:
            self.content = updatedData["content"]
        if updatedData.get("embeds") is not None:
            embeds: list[Embed] = []
            for embed in updatedData["embeds"]:
                embeds.append(await Embed.FromJSON(json.dumps(embed)))
            self.embeds = embeds
        if updatedData.get("mentions") is not None:
            mentions: list[User] = []
            for mention in updatedData["mentions"]:
                mentions.append(await User.FromJSON(json.dumps(mention), self.session))
            self.mentions = mentions
        if updatedData.get("replies") is not None:
            replies: list[Message] = []
            for reply in updatedData["replies"]:
                replies.append(await Message.FromJSON(json.dumps(reply), self.session))
            self.replies = replies
        if updatedData.get("masquerade") is not None:
            self.masquerade = await Masquerade.FromJSON(json.dumps(updatedData["masquerade"]))

    @property
    def url(self) -> str:
        return f"https://app.revolt.chat/channel/{self.channel.channelID}/{self.messageID}"

    @staticmethod
    async def FromJSON(jsonData: str | bytes, session: Session) -> Message:
        data: dict = json.loads(jsonData)
        kwargs: dict = {}
        kwargs["session"] = session
        if data.get("content") is not None:
            kwargs["content"] = data["content"]
        if data.get("nonce") is not None:
            kwargs["nonce"] = data["nonce"]
        if data.get("edited") is not None:
            kwargs["edited"] = data["edited"]
        if data.get("embeds") is not None:
            kwargs["embeds"] = []
            for embed in data["embeds"]:
                kwargs["embeds"].append(await Embed.FromJSON(json.dumps(embed)))
        if data.get("mentions") is not None:
            kwargs["mentions"] = []
            for mention in data["mentions"]:
                kwargs["mentions"].append(await User.FromID(mention, session))
        if data.get("replies") is not None:
            kwargs["replies"] = []
            for reply in data["replies"]:
                kwargs["replies"].append(await Message.FromID(data["channel"], reply, session))
        if data.get("masquerade") is not None:
            kwargs["masquerade"] = await Masquerade.FromJSON(json.dumps(data["masquerade"]))
        message: Message = Message(data["_id"], await Channel.FromID(data["channel"], session), await User.FromID(data["author"], session), **kwargs)
        session.messages[data["_id"]] = message
        return message

    @staticmethod
    async def FromID(channelID: str, messageID: str, session: Session) -> Message:
        if session.messages.get(messageID) is not None:
            return session.messages[messageID]
        data: dict = await session.Request(Method.GET, f"/channels/{channelID}/messages/{messageID}")
        if data.get("type") is not None:
            return
        return await Message.FromJSON(json.dumps(data), session)

    @staticmethod
    async def generateMessageData(**kwargs) -> dict:
        data: dict = {}
        if kwargs.get("content") is None and kwargs.get("embeds") is None and kwargs.get("embed") is None:
            raise InvalidMessageException("Message must have content or embed")

        if kwargs.get("content") is not None:
            data["content"] = kwargs["content"]
        if kwargs.get("replies") is not None:
            data["replies"] = []
            for reply in kwargs["replies"]:
                data["replies"].append({"id": reply.messageID, "mention": reply.mention})
        if kwargs.get("embed") is not None:
            data["embeds"] = [json.loads(kwargs["embed"].toJSON())]
        if kwargs.get("embeds") is not None:
            data["embeds"] = data.get("embeds", [])
            for embed in kwargs["embeds"]:
                data["embeds"].append(json.loads(embed.toJSON()))
        if kwargs.get("masquerade") is not None:
            data["masquerade"] = {"id": kwargs["masquerade"].name, "avatar": kwargs["masquerade"].avatar}
        return data

    async def Send(self, **kwargs) -> Message:
        data: dict = await Message.generateMessageData(**kwargs)
        await Message.FromJSON(json.dumps(await self.session.Request(Method.POST, f"/channels/{self.channel.channelID}/messages", data=data)), self.session)

    async def Edit(self, **kwargs) -> None:
        data: dict = {}
        if kwargs.get("content") is not None:
            data["content"] = kwargs["content"]
        if kwargs.get("embed") is not None:
            data["embeds"] = [json.loads(kwargs["embed"].toJSON())]
        if kwargs.get("embeds") is not None:
            data["embeds"] = data.get("embeds", [])
            for embed in kwargs["embeds"]:
                data["embeds"].append(json.loads(embed.toJSON()))

        result: dict = await self.session.Request(Method.PATCH, f"/channels/{self.channel.channelID}/messages/{self.messageID}", data=data)
        if result.get("type") is None:
            await self.update(result)

    async def Delete(self) -> None:
        if self.author is self.session.self:
            await self.session.Request(Method.DELETE, f"/channels/{self.channel.channelID}/messages/{self.messageID}")
        else:
            if self.channel.type == ChannelType.SavedMessages | ChannelType.DirectMessage | ChannelType.Group:
                raise TypeError("You can only delete messages by yourself from non-server channels.")
            else:
                request: dict = await self.session.Request(Method.DELETE, f"/channels/{self.channel.channelID}/messages/{self.messageID}")
                if request.get("type") == "MissingPermission":
                    raise PermissionError(f"You are missing the {request['permission']} permission.")
                self.session.messages.pop(self.messageID)

    @staticmethod
    async def Create(channel: Channel, **kwargs) -> Message:
        return await Message.FromJSON(json.dumps(await channel.session.Request(Method.POST, f"/channels/{channel.channelID}/messages", data=await Message.generateMessageData(**kwargs))), channel.session)
