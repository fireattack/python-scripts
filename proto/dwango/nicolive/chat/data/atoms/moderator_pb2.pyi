"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import collections.abc
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.internal.enum_type_wrapper
import google.protobuf.message
import google.protobuf.timestamp_pb2
import sys
import typing

if sys.version_info >= (3, 10):
    import typing as typing_extensions
else:
    import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing.final
class ModeratorUserInfo(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    USER_ID_FIELD_NUMBER: builtins.int
    NICKNAME_FIELD_NUMBER: builtins.int
    ICONURL_FIELD_NUMBER: builtins.int
    user_id: builtins.int
    nickname: builtins.str
    iconUrl: builtins.str
    def __init__(
        self,
        *,
        user_id: builtins.int = ...,
        nickname: builtins.str | None = ...,
        iconUrl: builtins.str | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["_iconUrl", b"_iconUrl", "_nickname", b"_nickname", "iconUrl", b"iconUrl", "nickname", b"nickname"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["_iconUrl", b"_iconUrl", "_nickname", b"_nickname", "iconUrl", b"iconUrl", "nickname", b"nickname", "user_id", b"user_id"]) -> None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_iconUrl", b"_iconUrl"]) -> typing.Literal["iconUrl"] | None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_nickname", b"_nickname"]) -> typing.Literal["nickname"] | None: ...

global___ModeratorUserInfo = ModeratorUserInfo

@typing.final
class ModeratorUpdated(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _ModeratorOperation:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _ModeratorOperationEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[ModeratorUpdated._ModeratorOperation.ValueType], builtins.type):
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        ADD: ModeratorUpdated._ModeratorOperation.ValueType  # 0
        DELETE: ModeratorUpdated._ModeratorOperation.ValueType  # 1

    class ModeratorOperation(_ModeratorOperation, metaclass=_ModeratorOperationEnumTypeWrapper): ...
    ADD: ModeratorUpdated.ModeratorOperation.ValueType  # 0
    DELETE: ModeratorUpdated.ModeratorOperation.ValueType  # 1

    OPERATION_FIELD_NUMBER: builtins.int
    OPERATOR_FIELD_NUMBER: builtins.int
    UPDATEDAT_FIELD_NUMBER: builtins.int
    operation: global___ModeratorUpdated.ModeratorOperation.ValueType
    @property
    def operator(self) -> global___ModeratorUserInfo: ...
    @property
    def updatedAt(self) -> google.protobuf.timestamp_pb2.Timestamp: ...
    def __init__(
        self,
        *,
        operation: global___ModeratorUpdated.ModeratorOperation.ValueType = ...,
        operator: global___ModeratorUserInfo | None = ...,
        updatedAt: google.protobuf.timestamp_pb2.Timestamp | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["operator", b"operator", "updatedAt", b"updatedAt"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["operation", b"operation", "operator", b"operator", "updatedAt", b"updatedAt"]) -> None: ...

global___ModeratorUpdated = ModeratorUpdated

@typing.final
class SSNGUpdated(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _SSNGOperation:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _SSNGOperationEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[SSNGUpdated._SSNGOperation.ValueType], builtins.type):
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        ADD: SSNGUpdated._SSNGOperation.ValueType  # 0
        DELETE: SSNGUpdated._SSNGOperation.ValueType  # 1

    class SSNGOperation(_SSNGOperation, metaclass=_SSNGOperationEnumTypeWrapper): ...
    ADD: SSNGUpdated.SSNGOperation.ValueType  # 0
    DELETE: SSNGUpdated.SSNGOperation.ValueType  # 1

    class _SSNGType:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _SSNGTypeEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[SSNGUpdated._SSNGType.ValueType], builtins.type):
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        USER: SSNGUpdated._SSNGType.ValueType  # 0
        WORD: SSNGUpdated._SSNGType.ValueType  # 1
        COMMAND: SSNGUpdated._SSNGType.ValueType  # 2

    class SSNGType(_SSNGType, metaclass=_SSNGTypeEnumTypeWrapper): ...
    USER: SSNGUpdated.SSNGType.ValueType  # 0
    WORD: SSNGUpdated.SSNGType.ValueType  # 1
    COMMAND: SSNGUpdated.SSNGType.ValueType  # 2

    OPERATION_FIELD_NUMBER: builtins.int
    SSNG_ID_FIELD_NUMBER: builtins.int
    OPERATOR_FIELD_NUMBER: builtins.int
    TYPE_FIELD_NUMBER: builtins.int
    SOURCE_FIELD_NUMBER: builtins.int
    UPDATEDAT_FIELD_NUMBER: builtins.int
    operation: global___SSNGUpdated.SSNGOperation.ValueType
    ssng_id: builtins.int
    type: global___SSNGUpdated.SSNGType.ValueType
    source: builtins.str
    @property
    def operator(self) -> global___ModeratorUserInfo: ...
    @property
    def updatedAt(self) -> google.protobuf.timestamp_pb2.Timestamp: ...
    def __init__(
        self,
        *,
        operation: global___SSNGUpdated.SSNGOperation.ValueType = ...,
        ssng_id: builtins.int = ...,
        operator: global___ModeratorUserInfo | None = ...,
        type: global___SSNGUpdated.SSNGType.ValueType | None = ...,
        source: builtins.str | None = ...,
        updatedAt: google.protobuf.timestamp_pb2.Timestamp | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["_source", b"_source", "_type", b"_type", "_updatedAt", b"_updatedAt", "operator", b"operator", "source", b"source", "type", b"type", "updatedAt", b"updatedAt"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["_source", b"_source", "_type", b"_type", "_updatedAt", b"_updatedAt", "operation", b"operation", "operator", b"operator", "source", b"source", "ssng_id", b"ssng_id", "type", b"type", "updatedAt", b"updatedAt"]) -> None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_source", b"_source"]) -> typing.Literal["source"] | None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_type", b"_type"]) -> typing.Literal["type"] | None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_updatedAt", b"_updatedAt"]) -> typing.Literal["updatedAt"] | None: ...

global___SSNGUpdated = SSNGUpdated

@typing.final
class ModerationAnnouncement(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _GuidelineItem:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _GuidelineItemEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[ModerationAnnouncement._GuidelineItem.ValueType], builtins.type):
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        UNKNOWN: ModerationAnnouncement._GuidelineItem.ValueType  # 0
        SEXUAL: ModerationAnnouncement._GuidelineItem.ValueType  # 1
        SPAM: ModerationAnnouncement._GuidelineItem.ValueType  # 2
        SLANDER: ModerationAnnouncement._GuidelineItem.ValueType  # 3
        PERSONAL_INFORMATION: ModerationAnnouncement._GuidelineItem.ValueType  # 4

    class GuidelineItem(_GuidelineItem, metaclass=_GuidelineItemEnumTypeWrapper): ...
    UNKNOWN: ModerationAnnouncement.GuidelineItem.ValueType  # 0
    SEXUAL: ModerationAnnouncement.GuidelineItem.ValueType  # 1
    SPAM: ModerationAnnouncement.GuidelineItem.ValueType  # 2
    SLANDER: ModerationAnnouncement.GuidelineItem.ValueType  # 3
    PERSONAL_INFORMATION: ModerationAnnouncement.GuidelineItem.ValueType  # 4

    MESSAGE_FIELD_NUMBER: builtins.int
    GUIDELINEITEMS_FIELD_NUMBER: builtins.int
    UPDATEDAT_FIELD_NUMBER: builtins.int
    message: builtins.str
    @property
    def guidelineItems(self) -> google.protobuf.internal.containers.RepeatedScalarFieldContainer[global___ModerationAnnouncement.GuidelineItem.ValueType]: ...
    @property
    def updatedAt(self) -> google.protobuf.timestamp_pb2.Timestamp: ...
    def __init__(
        self,
        *,
        message: builtins.str | None = ...,
        guidelineItems: collections.abc.Iterable[global___ModerationAnnouncement.GuidelineItem.ValueType] | None = ...,
        updatedAt: google.protobuf.timestamp_pb2.Timestamp | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["_message", b"_message", "message", b"message", "updatedAt", b"updatedAt"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["_message", b"_message", "guidelineItems", b"guidelineItems", "message", b"message", "updatedAt", b"updatedAt"]) -> None: ...
    def WhichOneof(self, oneof_group: typing.Literal["_message", b"_message"]) -> typing.Literal["message"] | None: ...

global___ModerationAnnouncement = ModerationAnnouncement