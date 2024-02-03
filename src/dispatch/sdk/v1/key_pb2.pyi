from typing import ClassVar as _ClassVar
from typing import Iterable as _Iterable
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class CreateSigningKeyRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CreateSigningKeyResponse(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: SigningKey
    def __init__(self, key: _Optional[_Union[SigningKey, _Mapping]] = ...) -> None: ...

class DeleteSigningKeyRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteSigningKeyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListSigningKeysRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListSigningKeysResponse(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedCompositeFieldContainer[SigningKey]
    def __init__(
        self, keys: _Optional[_Iterable[_Union[SigningKey, _Mapping]]] = ...
    ) -> None: ...

class SigningKey(_message.Message):
    __slots__ = ("public_key",)
    PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    public_key: bytes
    def __init__(self, public_key: _Optional[bytes] = ...) -> None: ...
