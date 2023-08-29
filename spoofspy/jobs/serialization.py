from typing import Any

import msgpack


def dumps(obj: Any) -> bytes:
    return msgpack.packb(
        obj,
        datetime=True,
    )


def loads(value: bytes) -> Any:
    return msgpack.unpackb(
        value,
        timestamp=3,
    )
