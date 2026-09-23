"""把分块到达的字节还原成一条条 NDJSON 记录。"""

import json

from .errors import StreamDecodeError

#: UTF-8 BOM，只允许出现在流的最开头。
_BOM = b"\xef\xbb\xbf"

#: 已确认消费掉的前缀超过这个长度就搬一次缓冲区，避免 bytearray 无限增长。
_RECLAIM_AT = 64 * 1024


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
        # 未消费的原始字节。分行在字节层完成：UTF-8 的续字节都 >= 0x80，
        # 不可能等于 0x0A，所以按 b"\n" 切分永远不会切坏多字节字符。
        self._buf = bytearray()
        # _tail_start：当前半行的起点；_scan_from：下一次找换行的起点。
        # 两者分开才能在 1 字节块下只扫描新到的字节（整体 O(n)）。
        self._tail_start = 0
        self._scan_from = 0
        self._bom_done = False
        self._count = 0
        self._closed = False

    # -- 输入 ---------------------------------------------------------

    def feed(self, chunk):
        """喂入一段字节，返回本次能完整解析出的记录（可能为空列表）。"""
        if self._closed:
            raise RuntimeError("reader 已经 close()，不能再 feed()")
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("feed() 只接受 bytes，收到 %s" % type(chunk).__name__)
        if not chunk:
            return []
        self._buf.extend(chunk)
        return self._drain()

    def close(self):
        """声明输入结束，返回剩余记录。可以重复调用。"""
        if self._closed:
            return []
        self._closed = True
        self._consume_bom()
        raw = bytes(self._buf[self._tail_start:])
        self._buf.clear()
        self._tail_start = 0
        self._scan_from = 0
        if not raw:
            return []
        record = self._record_from_line(raw)
        return [] if record is None else [record]

    # -- 内部 ---------------------------------------------------------

    def _drain(self):
        self._consume_bom()
        buf = self._buf
        out = []
        nl = buf.find(b"\n", self._scan_from)
        while nl >= 0:
            record = self._record_from_line(bytes(buf[self._tail_start:nl]))
            if record is not None:
                out.append(record)
            self._tail_start = nl + 1
            self._scan_from = self._tail_start
            nl = buf.find(b"\n", self._scan_from)
        # 没有更多换行了：半行从 _tail_start 留起，扫描游标顶到末尾，
        # 下次 feed 只扫新字节。
        self._scan_from = len(buf)
        if self._tail_start >= _RECLAIM_AT:
            del buf[:self._tail_start]
            self._scan_from -= self._tail_start
            self._tail_start = 0
        return out

    def _consume_bom(self):
        """处理流开头的 BOM；字节不够 3 个时先留着等下一块。"""
        if self._bom_done:
            return
        buf = self._buf
        if len(buf) < len(_BOM):
            return
        if buf[:len(_BOM)] == _BOM:
            # BOM 判定一定发生在任何分行扫描之前，偏移量归零即可。
            del buf[:len(_BOM)]
            self._tail_start = 0
            self._scan_from = 0
        self._bom_done = True

    def _record_from_line(self, raw):
        """把一整行（不含 ``\n``）解码成记录；空行返回 ``None``。"""
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StreamDecodeError(
                "第 %d 条之后的记录不是合法 UTF-8: %s" % (self._count, exc)
            ) from exc
        text = text.strip()
        if not text:
            return None
        try:
            value = json.loads(text)
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
