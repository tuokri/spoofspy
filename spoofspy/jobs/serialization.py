import msgpack


def dumps(obj):
    return msgpack.packb(
        obj,
        datetime=True,
    )


def loads(obj):
    return msgpack.unpackb(
        obj,
        timestamp=3,
    )
