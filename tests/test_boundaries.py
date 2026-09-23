"""切块等价性与各种边界的补充用例（原有测试未覆盖 UTF-8 字符边界 / BOM / U+2028）。"""

import json
import unittest

from streamndjson import NDJSONReader, StreamDecodeError


def line(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def read_chunked(payload, size):
    reader = NDJSONReader()
    out = []
    for start in range(0, len(payload), size):
        out.extend(reader.feed(payload[start:start + size]))
    out.extend(reader.close())
    return out


def mixed_payload():
    parts = [
        b"\xef\xbb\xbf",
        line({"id": 1}) + b"\r\n",
        line({"id": 2, "s": "行\u2028分隔\u2029符"}) + b"\n",
        b"\n",
        line({"id": 3, "e": "emoji 🚀 中文"}) + b"\n",
        b"\r\n",
        line({"id": 4}) + b"   \n",
        line({"id": 5}),  # 最后一行没有结尾换行
    ]
    return b"".join(parts)


class EquivalenceTest(unittest.TestCase):
    def test_all_chunk_sizes_match_one_shot(self):
        payload = mixed_payload()
        baseline = read_chunked(payload, len(payload) + 1)
        self.assertEqual([r["id"] for r in baseline], [1, 2, 3, 4, 5])
        self.assertEqual(baseline[1]["s"], "行\u2028分隔\u2029符")
        for size in list(range(1, 33)) + [64, 997, 8192]:
            self.assertEqual(read_chunked(payload, size), baseline)

    def test_bom_split_at_every_byte(self):
        payload = b"\xef\xbb\xbf" + line({"a": 1})
        for cut in range(4):
            reader = NDJSONReader()
            got = reader.feed(payload[:cut])
            got.extend(reader.feed(payload[cut:]))
            got.extend(reader.close())
            self.assertEqual(got, [{"a": 1}])

    def test_multibyte_char_split_at_every_byte(self):
        payload = '{"s": "中🚀"}\n'.encode("utf-8")
        for cut in range(len(payload)):
            reader = NDJSONReader()
            got = reader.feed(payload[:cut])
            got.extend(reader.feed(payload[cut:]))
            got.extend(reader.close())
            self.assertEqual(got, [{"s": "中🚀"}], cut)

    def test_u2028_is_not_a_line_separator(self):
        payload = line({"s": "a\u2028b\u2029c"})
        for size in (1, 2, 3, len(payload)):
            self.assertEqual(read_chunked(payload, size), [{"s": "a\u2028b\u2029c"}])


class CloseTailTest(unittest.TestCase):
    def test_close_returns_unterminated_last_record(self):
        reader = NDJSONReader()
        self.assertEqual(reader.feed(b'{"a": 1}\n{"a":'), [{"a": 1}])
        self.assertEqual(reader.feed(b' 2}'), [])
        self.assertEqual(reader.close(), [{"a": 2}])
        self.assertEqual(reader.count, 2)

    def test_close_on_blank_tail_returns_empty(self):
        reader = NDJSONReader()
        reader.feed(b'{"a": 1}\n  \r\n')
        self.assertEqual(reader.close(), [])

    def test_incomplete_bom_only_tail_raises(self):
        reader = NDJSONReader()
        reader.feed(b"\xef")
        with self.assertRaises(StreamDecodeError):
            reader.close()


class ErrorEquivalenceTest(unittest.TestCase):
    def _expect_error(self, payload, size):
        reader = NDJSONReader()
        with self.assertRaises(StreamDecodeError):
            for start in range(0, len(payload), size):
                reader.feed(payload[start:start + size])
            reader.close()

    def test_bad_utf8_raises_stream_error_one_byte_at_a_time(self):
        self._expect_error(line({"a": 1}) + b'{"x": "\xff"}\n', 1)

    def test_bad_utf8_in_unterminated_tail_raises_on_close(self):
        self._expect_error(line({"a": 1}) + b'{"x": "\xff"}', 1)

    def test_bad_json_in_unterminated_tail_raises_on_close(self):
        self._expect_error(line({"a": 1}) + b'{"x": ', 1)

    def test_lone_cr_is_not_a_line_separator(self):
        self._expect_error(b'{"a": 1}\r{"b": 2}\n', 1)


if __name__ == "__main__":
    unittest.main()
