import json
import unittest

from streamndjson import NDJSONReader, StreamDecodeError


def line(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"


class FeedTest(unittest.TestCase):
    def setUp(self):
        self.reader = NDJSONReader()

    def test_single_record(self):
        self.assertEqual(self.reader.feed(line({"a": 1})), [{"a": 1}])

    def test_several_records_in_one_chunk(self):
        raw = line({"a": 1}) + line({"a": 2}) + line({"a": 3})
        self.assertEqual(self.reader.feed(raw), [{"a": 1}, {"a": 2}, {"a": 3}])

    def test_record_split_across_two_chunks(self):
        first = self.reader.feed(b'{"a": 1}\n{"a":')
        second = self.reader.feed(b' 2}\n')
        self.assertEqual(first, [{"a": 1}])
        self.assertEqual(second, [{"a": 2}])

    def test_chunk_without_newline_yields_nothing(self):
        self.assertEqual(self.reader.feed(b'{"a": 1}'), [])

    def test_empty_chunk_is_noop(self):
        self.assertEqual(self.reader.feed(b""), [])

    def test_blank_lines_are_skipped(self):
        self.assertEqual(self.reader.feed(b'\n\n{"a": 1}\n\n'), [{"a": 1}])

    def test_whitespace_only_line_is_skipped(self):
        self.assertEqual(self.reader.feed(b'   \n{"a": 1}\n'), [{"a": 1}])

    def test_crlf_line_endings(self):
        self.assertEqual(
            self.reader.feed(b'{"a": 1}\r\n{"a": 2}\r\n'), [{"a": 1}, {"a": 2}]
        )

    def test_crlf_split_across_chunks(self):
        self.assertEqual(self.reader.feed(b'{"a": 1}\r'), [])
        self.assertEqual(self.reader.feed(b'\n{"a": 2}\r\n'), [{"a": 1}, {"a": 2}])

    def test_utf8_value(self):
        self.assertEqual(
            self.reader.feed('{"城市": "北京"}\n'.encode("utf-8")),
            [{"城市": "北京"}],
        )

    def test_nested_values(self):
        self.assertEqual(
            self.reader.feed(b'{"a": {"b": [1, 2, {"c": null}]}}\n'),
            [{"a": {"b": [1, 2, {"c": None}]}}],
        )

    def test_count_tracks_yielded_records(self):
        self.reader.feed(line({"a": 1}) + line({"a": 2}))
        self.assertEqual(self.reader.count, 2)

    def test_count_ignores_blank_lines(self):
        self.reader.feed(b'\n{"a": 1}\n\n')
        self.assertEqual(self.reader.count, 1)

    def test_invalid_json_raises(self):
        with self.assertRaises(StreamDecodeError):
            self.reader.feed(b'{"a": }\n')

    def test_non_object_line_raises(self):
        with self.assertRaises(StreamDecodeError):
            self.reader.feed(b'[1, 2, 3]\n')

    def test_feed_rejects_text(self):
        with self.assertRaises(TypeError):
            self.reader.feed("not bytes")

    def test_feed_after_close_raises(self):
        self.reader.close()
        with self.assertRaises(RuntimeError):
            self.reader.feed(b'{"a": 1}\n')

    def test_close_is_idempotent(self):
        self.reader.feed(line({"a": 1}))
        self.reader.close()
        self.assertEqual(self.reader.close(), [])


class ChunkBoundaryTest(unittest.TestCase):
    """同一份数据按不同块大小喂进去，结果必须一致。

    这里的样例记录全是 ASCII，所以块边界可以任意切。
    """

    payload = (
        line({"id": 1, "msg": "ok"})
        + line({"id": 2, "msg": "ok"})
        + line({"id": 3, "msg": "ok"})
    )

    def _read_all(self, size):
        reader = NDJSONReader()
        out = []
        for start in range(0, len(self.payload), size):
            out.extend(reader.feed(self.payload[start:start + size]))
        out.extend(reader.close())
        return out

    def test_size_one(self):
        self.assertEqual(len(self._read_all(1)), 3)

    def test_size_two(self):
        self.assertEqual(len(self._read_all(2)), 3)

    def test_size_larger_than_payload(self):
        self.assertEqual(len(self._read_all(4096)), 3)

    def test_size_matching_record_length(self):
        record_len = len(line({"id": 1, "msg": "ok"}))
        self.assertEqual(len(self._read_all(record_len)), 3)


if __name__ == "__main__":
    unittest.main()
