# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: dwango/nicolive/chat/data/state.proto
# Protobuf Python Version: 5.27.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    0,
    '',
    'dwango/nicolive/chat/data/state.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import atoms_pb2 as dwango_dot_nicolive_dot_chat_dot_data_dot_atoms__pb2
from .atoms import moderator_pb2 as dwango_dot_nicolive_dot_chat_dot_data_dot_atoms_dot_moderator__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n%dwango/nicolive/chat/data/state.proto\x12\x19\x64wango.nicolive.chat.data\x1a%dwango/nicolive/chat/data/atoms.proto\x1a/dwango/nicolive/chat/data/atoms/moderator.proto\"\x86\x06\n\rNicoliveState\x12>\n\nstatistics\x18\x01 \x01(\x0b\x32%.dwango.nicolive.chat.data.StatisticsH\x00\x88\x01\x01\x12\x38\n\x07\x65nquete\x18\x02 \x01(\x0b\x32\".dwango.nicolive.chat.data.EnqueteH\x01\x88\x01\x01\x12=\n\nmove_order\x18\x03 \x01(\x0b\x32$.dwango.nicolive.chat.data.MoveOrderH\x02\x88\x01\x01\x12\x38\n\x07marquee\x18\x04 \x01(\x0b\x32\".dwango.nicolive.chat.data.MarqueeH\x03\x88\x01\x01\x12\x41\n\x0c\x63omment_lock\x18\x05 \x01(\x0b\x32&.dwango.nicolive.chat.data.CommentLockH\x04\x88\x01\x01\x12\x41\n\x0c\x63omment_mode\x18\x06 \x01(\x0b\x32&.dwango.nicolive.chat.data.CommentModeH\x05\x88\x01\x01\x12?\n\x0btrial_panel\x18\x07 \x01(\x0b\x32%.dwango.nicolive.chat.data.TrialPanelH\x06\x88\x01\x01\x12\x45\n\x0eprogram_status\x18\t \x01(\x0b\x32(.dwango.nicolive.chat.data.ProgramStatusH\x07\x88\x01\x01\x12]\n\x17moderation_announcement\x18\n \x01(\x0b\x32\x37.dwango.nicolive.chat.data.atoms.ModerationAnnouncementH\x08\x88\x01\x01\x42\r\n\x0b_statisticsB\n\n\x08_enqueteB\r\n\x0b_move_orderB\n\n\x08_marqueeB\x0f\n\r_comment_lockB\x0f\n\r_comment_modeB\x0e\n\x0c_trial_panelB\x11\n\x0f_program_statusB\x1a\n\x18_moderation_announcementb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'dwango.nicolive.chat.data.state_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_NICOLIVESTATE']._serialized_start=157
  _globals['_NICOLIVESTATE']._serialized_end=931
# @@protoc_insertion_point(module_scope)
