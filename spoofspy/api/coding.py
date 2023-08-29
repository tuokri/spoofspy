import ipaddress
from typing import Any

import msgpack
import zstandard as zstd
from fastapi_cache import Coder

from spoofspy import db

_EXT_TYPE_IPV4ADDRESS = 0


def _default_encode(obj: Any) -> Any:
    if isinstance(obj, db.models.BaseModel):
        return {
            "__sql_class__": obj.__class__.__name__,
            "data": obj.to_dict(ignore_unloaded=True),
        }
    elif isinstance(obj, ipaddress.IPv4Address):
        return msgpack.ExtType(
            _EXT_TYPE_IPV4ADDRESS,
            obj.packed,
        )
    return obj


def _object_hook(obj: Any) -> Any:
    if "__sql_class__" in obj:
        cls = getattr(db.models, obj["__sql_class__"])
        return cls(**obj["data"])
    return obj


def _ext_hook(code: int, data: bytes) -> Any:
    if code == _EXT_TYPE_IPV4ADDRESS:
        return ipaddress.IPv4Address(data)
    return msgpack.ExtType(code, data)


class MsgPackCoder(Coder):
    @classmethod
    # type: ignore[override]
    def encode(cls, value: Any) -> bytes:
        return msgpack.packb(
            value,
            datetime=True,
            default=_default_encode,
        )

    @classmethod
    # type: ignore[override]
    def decode(cls, value: bytes) -> Any:
        return msgpack.unpackb(
            value,
            timestamp=3,
            use_list=False,
            object_hook=_object_hook,
            ext_hook=_ext_hook,
            raw=True,
        )


class ZstdMsgPackCoder(MsgPackCoder):
    @classmethod
    # type: ignore[override]
    def encode(cls, value: Any) -> bytes:
        return zstd.compress(super().encode(value))

    @classmethod
    # type: ignore[override]
    def decode(cls, value: bytes) -> Any:
        return super().decode(zstd.decompress(value))
