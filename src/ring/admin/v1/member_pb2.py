# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: ring/admin/v1/member.proto
# Protobuf Python Version: 4.25.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1aring/admin/v1/member.proto\x12\rring.admin.v1\x1a\x1fgoogle/protobuf/timestamp.proto\"\xb5\x02\n\x0bMemberState\x12\x41\n\tinstances\x18\x01 \x03(\x0b\x32#.ring.admin.v1.MemberState.InstanceR\tinstances\x12\x44\n\npartitions\x18\x02 \x03(\x0b\x32$.ring.admin.v1.MemberState.PartitionR\npartitions\x1aH\n\x08Instance\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\x12,\n\x03ttl\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.TimestampR\x03ttl\x1aS\n\tPartition\x12\x16\n\x06number\x18\x01 \x01(\x05R\x06number\x12\x14\n\x05owner\x18\x02 \x01(\tR\x05owner\x12\x18\n\x07\x63reator\x18\x03 \x01(\tR\x07\x63reator\"\x14\n\x12MemberStateRequest\"G\n\x13MemberStateResponse\x12\x30\n\x05state\x18\x01 \x01(\x0b\x32\x1a.ring.admin.v1.MemberStateR\x05state2j\n\rMemberService\x12Y\n\x0bMemberState\x12!.ring.admin.v1.MemberStateRequest\x1a\".ring.admin.v1.MemberStateResponse\"\x03\x90\x02\x01\x42v\n\x11\x63om.ring.admin.v1B\x0bMemberProtoP\x01\xa2\x02\x03RAX\xaa\x02\rRing.Admin.V1\xca\x02\rRing\\Admin\\V1\xe2\x02\x19Ring\\Admin\\V1\\GPBMetadata\xea\x02\x0fRing::Admin::V1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'ring.admin.v1.member_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  _globals['DESCRIPTOR']._options = None
  _globals['DESCRIPTOR']._serialized_options = b'\n\021com.ring.admin.v1B\013MemberProtoP\001\242\002\003RAX\252\002\rRing.Admin.V1\312\002\rRing\\Admin\\V1\342\002\031Ring\\Admin\\V1\\GPBMetadata\352\002\017Ring::Admin::V1'
  _globals['_MEMBERSERVICE'].methods_by_name['MemberState']._options = None
  _globals['_MEMBERSERVICE'].methods_by_name['MemberState']._serialized_options = b'\220\002\001'
  _globals['_MEMBERSTATE']._serialized_start=79
  _globals['_MEMBERSTATE']._serialized_end=388
  _globals['_MEMBERSTATE_INSTANCE']._serialized_start=231
  _globals['_MEMBERSTATE_INSTANCE']._serialized_end=303
  _globals['_MEMBERSTATE_PARTITION']._serialized_start=305
  _globals['_MEMBERSTATE_PARTITION']._serialized_end=388
  _globals['_MEMBERSTATEREQUEST']._serialized_start=390
  _globals['_MEMBERSTATEREQUEST']._serialized_end=410
  _globals['_MEMBERSTATERESPONSE']._serialized_start=412
  _globals['_MEMBERSTATERESPONSE']._serialized_end=483
  _globals['_MEMBERSERVICE']._serialized_start=485
  _globals['_MEMBERSERVICE']._serialized_end=591
# @@protoc_insertion_point(module_scope)
