"""按指定块大小回放一个 NDJSON 文件，逐条打印并统计。"""

import argparse
import sys
from pathlib import Path

from streamndjson import NDJSONReader, iter_chunks


def main(argv=None):
    parser = argparse.ArgumentParser(description="回放 NDJSON 文件")
    parser.add_argument("path", type=Path, help="要回放的文件")
    parser.add_argument("--block", type=int, default=8192, help="块大小（字节）")
    args = parser.parse_args(argv)

    reader = NDJSONReader()
    total = 0
    for chunk in iter_chunks(args.path, args.block):
        for record in reader.feed(chunk):
            total += 1
            print("%4d  %s" % (total, record))
    for record in reader.close():
        total += 1
        print("%4d  %s" % (total, record))

    print("-- 共 %d 条" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
