"""把分块到达的字节还原成一条条 NDJSON 记录。"""

import json

from .errors import StreamDecodeError

_BOM = b"\xef\xbb\xbf"
_NEWLINE = b"\n"

#: 已消费前缀超过这个阈值才搬移缓冲，避免残留大行时反复 memmove。
_COMPACT_THRESHOLD = 64 * 1024


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
    块边界可以落在任意字节上（包括多字节字符中间）。
    """

    def __init__(self):
        self._buf = bytearray()
        self._head = 0       # 缓冲里未消费数据的起点
        self._scan = 0       # 下一个待查找 \\n 的位置（之前的字节已确认不含 \\n）
        self._count = 0
        self._closed = False
        self._bom_done = False

    # -- 输入 ---------------------------------------------------------

    def feed(self, chunk):
        """喂入一段字节，返回本次能完整解析出的记录（可能为空列表）。"""
        if self._closed:
            raise RuntimeError("reader 已经 close()，不能再 feed()")
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("feed() 只接受 bytes，收到 %s" % type(chunk).__name__)
        self._buf += chunk
        return self._drain(final=False)

    def close(self):
        """声明输入结束，返回剩余记录。可以重复调用。"""
        if self._closed:
            return []
        self._closed = True
        return self._drain(final=True)

    # -- 内部 ---------------------------------------------------------

    def _drain(self, final):
        out = []
        if not self._strip_bom(final):
            # 缓冲里的字节还不足以判断是不是 BOM，等下一块。
            return out
        buf = self._buf
        while True:
            idx = buf.find(_NEWLINE, self._scan)
            if idx < 0:
                self._scan = len(buf)
                break
            record = self._parse_line(buf[self._head:idx])
            self._head = idx + 1
            self._scan = self._head
            if record is not None:
                out.append(record)
        if final:
            if self._head < len(buf):
                record = self._parse_line(buf[self._head:])
                if record is not None:
                    out.append(record)
            buf.clear()
            self._head = self._scan = 0
        elif self._head == len(buf):
            buf.clear()
            self._head = self._scan = 0
        elif self._head >= _COMPACT_THRESHOLD:
            del buf[:self._head]
            self._scan -= self._head
            self._head = 0
        return out

    def _strip_bom(self, final):
        """跳过流开头的 BOM；返回 False 表示现有字节不足以判断。"""
        if self._bom_done:
            return True
        avail = len(self._buf) - self._head
        if avail >= len(_BOM):
            if self._buf[self._head:self._head + len(_BOM)] == _BOM:
                self._head += len(_BOM)
                self._scan = max(self._scan, self._head)
            self._bom_done = True
            return True
        head = bytes(self._buf[self._head:])
        if not final and _BOM.startswith(head):
            return False
        self._bom_done = True
        return True

    def _parse_line(self, raw):
        """解析一整行；空白行返回 None。"""
        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StreamDecodeError(
                "第 %d 条记录不是合法 UTF-8: %s" % (self._count + 1, exc)
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
