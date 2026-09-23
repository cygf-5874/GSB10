"""把文件或字节串按固定大小切成块。

上游采集 agent 就是这么发数据的：不保证块边界落在行边界上。
"""

from pathlib import Path

#: 默认块大小，和上游 agent 的 socket 读缓冲一致。
DEFAULT_CHUNK_SIZE = 8192


def iter_chunks(source, size=DEFAULT_CHUNK_SIZE):
    """按 ``size`` 字节切块产出。

    ``source`` 可以是路径（``str`` / :class:`pathlib.Path`）或 ``bytes``。
    ``size`` 必须是正整数。
    """
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("size 必须是正整数")

    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        for start in range(0, len(data), size):
            yield data[start:start + size]
        return

    path = Path(source)
    with path.open("rb") as handle:
        while True:
            block = handle.read(size)
            if not block:
                break
            yield block
