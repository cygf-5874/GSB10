"""针对字节流边界情形的回归测试：任意块切分结果必须一致。"""

import json
import random
import unittest

from streamndjson import NDJSONReader, StreamDecodeError


def row(i, msg="ok"):
    return json.dumps(
        {"id": i, "msg": msg, "标签": "值%d" % i}, ensure_ascii=False
    ).encode("utf-8")


PAYLOAD = b"".join([
    b"\xef\xbb\xbf",                            # BOM
    row(1) + b"\r\n",                           # CRLF
    row(2, "行分隔符\u2028在字符串里") + b"\n",     # 未转义 U+2028
    b"\n",                                      # 空行
    row(3, "emoji 🚀 与中文") + b"\n",           # 多字节字符
    b"  \r\n",                                  # 纯空白行
    row(4) + b"   \n",                          # 尾随空白
    row(5),                                     # 最后一行没有换行
])


def read_all(payload, size):
    reader = NDJSONReader()
    out = []
    for start in range(0, len(payload), size):
        out.extend(reader.feed(payload[start:start + size]))
    out.extend(reader.close())
    return out


class ChunkInvarianceTest(unittest.TestCase):
    def test_every_size_matches_whole_payload(self):
        baseline = read_all(PAYLOAD, len(PAYLOAD))
        self.assertEqual(len(baseline), 5)
        for size in range(1, 70):
            self.assertEqual(read_all(PAYLOAD, size), baseline, "size=%d" % size)

    def test_random_chunkings_match(self):
        baseline = read_all(PAYLOAD, len(PAYLOAD))
        rng = random.Random(20260923)
        for _ in range(50):
            reader = NDJSONReader()
            out = []
            pos = 0
            while pos < len(PAYLOAD):
                step = rng.randint(1, 17)
                out.extend(reader.feed(PAYLOAD[pos:pos + step]))
                pos += step
            out.extend(reader.close())
            self.assertEqual(out, baseline)

    def test_u2028_inside_string_is_not_a_line_break(self):
        payload = row(1, "\u2028\u2029") + b"\n"
        for size in (1, 2, 3, len(payload)):
            got = read_all(payload, size)
            self.assertEqual(got, [{"id": 1, "msg": "\u2028\u2029", "标签": "值1"}])

    def test_close_flushes_trailing_line_without_newline(self):
        reader = NDJSONReader()
        self.assertEqual(reader.feed(b'{"a": 1}\n{"a": 2}'), [{"a": 1}])
        self.assertEqual(reader.close(), [{"a": 2}])
        self.assertEqual(reader.count, 2)

    def test_close_is_idempotent_after_flush(self):
        reader = NDJSONReader()
        reader.feed(b'{"a": 1}')
        self.assertEqual(reader.close(), [{"a": 1}])
        self.assertEqual(reader.close(), [])

    def test_bom_only_stream_yields_nothing(self):
        self.assertEqual(read_all(b"\xef\xbb\xbf", 1), [])

    def test_bom_split_across_chunks(self):
        reader = NDJSONReader()
        self.assertEqual(reader.feed(b"\xef"), [])
        self.assertEqual(reader.feed(b"\xbb"), [])
        self.assertEqual(reader.feed(b'\xbf{"a": 1}\n'), [{"a": 1}])

    def test_no_bom_prefix_is_decoded_normally(self):
        # 以 \xef 开头但不是 BOM 的流不能卡住；这里是非法 UTF-8，应报错。
        reader = NDJSONReader()
        with self.assertRaises(StreamDecodeError):
            reader.feed(b'\xef\x01{"a": 1}\n')

    def test_invalid_utf8_raises_stream_decode_error(self):
        reader = NDJSONReader()
        with self.assertRaises(StreamDecodeError):
            reader.feed(b'{"a": "\xff"}\n')

    def test_invalid_utf8_in_trailing_line_raises_on_close(self):
        reader = NDJSONReader()
        reader.feed(b'{"a": "')
        reader.feed(b"\xff")
        with self.assertRaises(StreamDecodeError):
            reader.close()

    def test_count_unchanged_after_failed_line(self):
        reader = NDJSONReader()
        reader.feed(b'{"a": 1}\n')
        with self.assertRaises(StreamDecodeError):
            reader.feed(b'{"a": }\n')
        self.assertEqual(reader.count, 1)


if __name__ == "__main__":
    unittest.main()
