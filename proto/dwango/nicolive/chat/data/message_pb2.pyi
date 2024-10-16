"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import ndgr_client.proto.dwango.nicolive.chat.data.atoms.moderator_pb2
import ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2
import google.protobuf.descriptor
import google.protobuf.message
import typing

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing.final
class NicoliveMessage(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    CHAT_FIELD_NUMBER: builtins.int
    SIMPLE_NOTIFICATION_FIELD_NUMBER: builtins.int
    GIFT_FIELD_NUMBER: builtins.int
    NICOAD_FIELD_NUMBER: builtins.int
    GAME_UPDATE_FIELD_NUMBER: builtins.int
    TAG_UPDATED_FIELD_NUMBER: builtins.int
    MODERATOR_UPDATED_FIELD_NUMBER: builtins.int
    SSNG_UPDATED_FIELD_NUMBER: builtins.int
    OVERFLOWED_CHAT_FIELD_NUMBER: builtins.int
    @property
    def chat(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Chat: ...
    @property
    def simple_notification(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.SimpleNotification: ...
    @property
    def gift(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Gift: ...
    @property
    def nicoad(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Nicoad: ...
    @property
    def game_update(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.GameUpdate: ...
    @property
    def tag_updated(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.TagUpdated: ...
    @property
    def moderator_updated(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms.moderator_pb2.ModeratorUpdated: ...
    @property
    def ssng_updated(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms.moderator_pb2.SSNGUpdated: ...
    @property
    def overflowed_chat(self) -> ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Chat: ...
    def __init__(
        self,
        *,
        chat: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Chat | None = ...,
        simple_notification: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.SimpleNotification | None = ...,
        gift: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Gift | None = ...,
        nicoad: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Nicoad | None = ...,
        game_update: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.GameUpdate | None = ...,
        tag_updated: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.TagUpdated | None = ...,
        moderator_updated: ndgr_client.proto.dwango.nicolive.chat.data.atoms.moderator_pb2.ModeratorUpdated | None = ...,
        ssng_updated: ndgr_client.proto.dwango.nicolive.chat.data.atoms.moderator_pb2.SSNGUpdated | None = ...,
        overflowed_chat: ndgr_client.proto.dwango.nicolive.chat.data.atoms_pb2.Chat | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["chat", b"chat", "data", b"data", "game_update", b"game_update", "gift", b"gift", "moderator_updated", b"moderator_updated", "nicoad", b"nicoad", "overflowed_chat", b"overflowed_chat", "simple_notification", b"simple_notification", "ssng_updated", b"ssng_updated", "tag_updated", b"tag_updated"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["chat", b"chat", "data", b"data", "game_update", b"game_update", "gift", b"gift", "moderator_updated", b"moderator_updated", "nicoad", b"nicoad", "overflowed_chat", b"overflowed_chat", "simple_notification", b"simple_notification", "ssng_updated", b"ssng_updated", "tag_updated", b"tag_updated"]) -> None: ...
    def WhichOneof(self, oneof_group: typing.Literal["data", b"data"]) -> typing.Literal["chat", "simple_notification", "gift", "nicoad", "game_update", "tag_updated", "moderator_updated", "ssng_updated", "overflowed_chat"] | None: ...

global___NicoliveMessage = NicoliveMessage