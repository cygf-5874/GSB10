import tempfile
import unittest
from pathlib import Path

from streamndjson import DEFAULT_CHUNK_SIZE, iter_chunks


class IterChunksTest(unittest.TestCase):
    def test_bytes_source_splits_evenly(self):
        self.assertEqual(list(iter_chunks(b"abcdef", 2)), [b"ab", b"cd", b"ef"])

    def test_last_chunk_may_be_short(self):
        self.assertEqual(list(iter_chunks(b"abcde", 2)), [b"ab", b"cd", b"e"])

    def test_empty_source_yields_nothing(self):
        self.assertEqual(list(iter_chunks(b"", 4)), [])

    def test_bytearray_source_is_accepted(self):
        self.assertEqual(list(iter_chunks(bytearray(b"abcd"), 4)), [b"abcd"])

    def test_default_chunk_size_is_used(self):
        self.assertEqual(DEFAULT_CHUNK_SIZE, 8192)

    def test_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            list(iter_chunks(b"ab", 0))

    def test_size_must_be_an_int(self):
        with self.assertRaises(ValueError):
            list(iter_chunks(b"ab", 1.5))

    def test_reads_file_by_path_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.ndjson"
            payload = b'{"a": 1}\n{"a": 2}\n'
            path.write_bytes(payload)
            chunks = list(iter_chunks(str(path), 5))
            self.assertEqual(b"".join(chunks), payload)

    def test_reads_file_by_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.ndjson"
            path.write_bytes(b"xyz")
            self.assertEqual(list(iter_chunks(path, 2)), [b"xy", b"z"])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            list(iter_chunks(Path("no") / "such" / "file.ndjson", 8))


if __name__ == "__main__":
    unittest.main()
