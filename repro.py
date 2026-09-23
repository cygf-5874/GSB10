"""上游给的复现脚本，别改。

采集 agent 实际用的是 9 字节一块（历史遗留的 socket 读缓冲），
拿 testdata/events.ndjson 回放就该读出 7 条。
"""

import sys
from pathlib import Path

from streamndjson import NDJSONReader, iter_chunks

DATA = Path(__file__).resolve().parent / "testdata" / "events.ndjson"
BLOCK_SIZE = 9
EXPECTED = 7


def main():
    reader = NDJSONReader()
    records = []
    try:
        for chunk in iter_chunks(DATA, BLOCK_SIZE):
            records.extend(reader.feed(chunk))
        records.extend(reader.close())
    except Exception as exc:                                    # noqa: BLE001
        print("读到第 %d 条时失败：%s: %s" % (len(records), type(exc).__name__, exc))
        print("期望 %d 条，实际 %d 条" % (EXPECTED, len(records)))
        return 1

    print("读到 %d 条，期望 %d 条" % (len(records), EXPECTED))
    print("id 序列:", [r.get("id") for r in records])
    if len(records) != EXPECTED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
