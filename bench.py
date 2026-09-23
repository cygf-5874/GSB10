"""固定基准入口 —— 别改这个文件。

    python3 bench.py --check     差分对拍：同一份数据按多种块大小读，结果必须一致。
    python3 bench.py --bench     长记录 + 1 字节块，必须在 TIME_LIMIT 秒内读完。

``--check`` 的样本刻意混了 BOM、CRLF、字符串里的 U+2028、纯空白行、
没有结尾换行的最后一行，以及多字节字符（中文 / emoji）。
``--bench`` 拿一条超长记录压 1 字节块的吞吐。
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from streamndjson import NDJSONReader                                  # noqa: E402

#: --check 要试的块大小
CHECK_SIZES = (1, 2, 3, 7, 9, 64, 997, 8192)

#: --bench 的块大小与数据规模
BENCH_BLOCK = 1
BENCH_ROWS = 2000
BENCH_LONG = 1024 * 1024          # 单条记录里 msg 字段的字节数
BENCH_EXPECTED = BENCH_ROWS + 1   # 2000 条普通记录 + 1 条超长记录

#: --bench 时限（秒）。按本机标定；换机器按同比例放宽。
TIME_LIMIT = 10.0


def _row(i, msg="ok"):
    return json.dumps(
        {"id": i, "msg": msg, "标签": "值%d" % i}, ensure_ascii=False
    ).encode("utf-8")


def check_payload():
    """混了各种边界的样本。"""
    parts = [
        b"\xef\xbb\xbf",                                       # 文件头 BOM
        _row(1) + b"\r\n",                                     # CRLF
        _row(2, "行分隔符\u2028在字符串里") + b"\n",             # 未转义的 U+2028
        b"\n",                                                 # 空行
        _row(3, "emoji 🚀 与中文") + b"\n",                     # 多字节
        b"\r\n",
        _row(4) + b"   \n",                                    # 尾随空白
        _row(5),                                               # 最后一行没有结尾换行
    ]
    return b"".join(parts)


def bench_payload():
    rows = [_row(i) for i in range(BENCH_ROWS // 2)]
    rows.append(_row(10 ** 6, "x" * BENCH_LONG))
    rows.extend(_row(i) for i in range(BENCH_ROWS // 2, BENCH_ROWS))
    return b"\n".join(rows) + b"\n"


def read_all(payload, size):
    reader = NDJSONReader()
    out = []
    for start in range(0, len(payload), size):
        out.extend(reader.feed(payload[start:start + size]))
    out.extend(reader.close())
    return out


def run_check():
    payload = check_payload()
    baseline = None
    baseline_size = None
    ok = True
    for size in CHECK_SIZES:
        try:
            got = read_all(payload, size)
        except Exception as exc:                               # noqa: BLE001
            print("块大小 %-5d 失败：%s: %s" % (size, type(exc).__name__, exc))
            ok = False
            continue
        if baseline is None:
            baseline, baseline_size = got, size
            print("块大小 %-5d 读出 %d 条（基准）" % (size, len(got)))
        elif got != baseline:
            print("块大小 %-5d 读出 %d 条，与块大小 %d 的结果不一致"
                  % (size, len(got), baseline_size))
            ok = False
        else:
            print("块大小 %-5d 读出 %d 条，一致" % (size, len(got)))
    print("--check:", "通过" if ok else "不通过")
    return 0 if ok else 1


def run_bench():
    payload = bench_payload()
    started = time.perf_counter()
    reader = NDJSONReader()
    seen = 0
    try:
        for start in range(0, len(payload), BENCH_BLOCK):
            seen += len(reader.feed(payload[start:start + BENCH_BLOCK]))
        seen += len(reader.close())
    except Exception as exc:                                   # noqa: BLE001
        print("--bench 失败：%s: %s" % (type(exc).__name__, exc))
        return 1
    elapsed = time.perf_counter() - started
    print("--bench: %d 字节、%d 字节/块 -> %d 条，用时 %.2fs（限 %.1fs）"
          % (len(payload), BENCH_BLOCK, seen, elapsed, TIME_LIMIT))
    if seen != BENCH_EXPECTED:
        print("--bench 条数不对：期望 %d，实际 %d" % (BENCH_EXPECTED, seen))
        return 1
    if elapsed > TIME_LIMIT:
        print("--bench 超时")
        return 1
    print("--bench: 通过")
    return 0


def main(argv):
    if argv and argv[0] == "--check":
        return run_check()
    if argv and argv[0] == "--bench":
        return run_bench()
    print("用法: python3 bench.py --check | --bench")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
