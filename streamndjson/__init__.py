"""分块字节流的 NDJSON 读取。

上游（日志采集 agent）按固定大小推块，这里把字节流还原成一条条记录。
只依赖标准库。
"""

from .errors import StreamDecodeError, StreamError
from .reader import NDJSONReader
from .source import DEFAULT_CHUNK_SIZE, iter_chunks

__all__ = [
    "NDJSONReader",
    "iter_chunks",
    "DEFAULT_CHUNK_SIZE",
    "StreamError",
    "StreamDecodeError",
]

__version__ = "0.3.1"
