"""把分块到达的字节还原成一条条 NDJSON 记录。"""

import json

from .errors import StreamDecodeError


class NDJSONReader:
    """增量解析换行分隔的 JSON 对象。

    用法::

        reader = NDJSONReader()
        for chunk in iter_chunks(path, 8192):
            for record in reader.feed(chunk):
                handle(record)
        for record in reader.close():
            handle(record)

    每一行必须是一个 JSON 对象；空行忽略；其余情况抛 :class:`StreamDecodeError`。
    """

    def __init__(self):
        self._buf = ""
        self._count = 0
        self._closed = False

    # -- 输入 ---------------------------------------------------------

    def feed(self, chunk):
        """喂入一段字节，返回本次能完整解析出的记录（可能为空列表）。"""
        if self._closed:
            raise RuntimeError("reader 已经 close()，不能再 feed()")
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("feed() 只接受 bytes，收到 %s" % type(chunk).__name__)
        self._buf += bytes(chunk).decode("utf-8")
        return self._drain()

    def close(self):
        """声明输入结束，返回剩余记录。可以重复调用。"""
        self._closed = True
        self._buf = ""
        return []

    # -- 内部 ---------------------------------------------------------

    def _drain(self):
        # 末尾没有换行的部分可能只是个半行，留到下一次 feed；前面的都是完整行。
        cut = self._buf.rfind("\n")
        if cut < 0:
            return []
        block, self._buf = self._buf[:cut], self._buf[cut + 1:]
        out = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(self._parse(line))
        return out

    def _parse(self, line):
        try:
            value = json.loads(line)
        except ValueError as exc:
            raise StreamDecodeError(
                "第 %d 条之后的记录不是合法 JSON: %s" % (self._count, exc)
            ) from exc
        if not isinstance(value, dict):
            raise StreamDecodeError("第 %d 条之后的记录不是 JSON 对象" % self._count)
        self._count += 1
        return value

    # -- 状态 ---------------------------------------------------------

    @property
    def count(self):
        """已经产出的记录条数。"""
        return self._count
