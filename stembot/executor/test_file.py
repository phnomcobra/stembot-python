"""Unit tests for stembot.executor.file.

Covers the complete file I/O round-trip:

    load_form_from_bytes  ->  write_file_from_form  ->  load_file_to_form  ->  load_bytes_from_form

All canonical values (b64zlib, md5sum, size) are hard-coded from fixed test
data so they can be ported verbatim to the equivalent executor tests in
stembot-rust and used to verify cross-language compatibility.

Protocol / format facts (for porting):
    TEST_DATA    = b"hello, stembot!"   (15 bytes, UTF-8 / raw bytes)
    TEST_MD5SUM  = "799be59fc7ab5d892640daa270a9715b"
    TEST_B64ZLIB = "eNrLSM3JyddRKC5JzU3KL1EEACz3BYA="
    TEST_SIZE    = 15

    b64zlib = base64( zlib_compress(data, level=9) )
    md5sum  = hex( md5(raw_data) )
"""
import hashlib
import os
import tempfile
import unittest
import zlib
from base64 import b64decode, b64encode

from stembot.executor.file import (
    load_bytes_from_form,
    load_file_to_form,
    load_form_from_bytes,
    write_file_from_form,
)
from stembot.models.control import LoadFile, WriteFile

# ---------------------------------------------------------------------------
# Canonical test fixtures — identical values must be used in stembot-rust
# ---------------------------------------------------------------------------

TEST_DATA    = b"hello, stembot!"
TEST_MD5SUM  = "799be59fc7ab5d892640daa270a9715b"
TEST_B64ZLIB = "eNrLSM3JyddRKC5JzU3KL1EEACz3BYA="
TEST_SIZE    = 15


# ---------------------------------------------------------------------------
# load_form_from_bytes
# ---------------------------------------------------------------------------

class TestLoadFormFromBytes(unittest.TestCase):
    """Verify that load_form_from_bytes produces the correct WriteFile form fields."""

    def setUp(self):
        self.form = load_form_from_bytes(TEST_DATA)

    def test_returns_write_file_instance(self):
        """Return value must be a WriteFile instance."""
        self.assertIsInstance(self.form, WriteFile)

    def test_size_is_correct(self):
        """size must equal the length of the original uncompressed data."""
        self.assertEqual(self.form.size, TEST_SIZE)

    def test_md5sum_is_correct(self):
        """md5sum must equal the hex MD5 digest of the original data."""
        self.assertEqual(self.form.md5sum, TEST_MD5SUM)

    def test_b64zlib_is_correct(self):
        """b64zlib must equal base64(zlib_compress(data, level=9))."""
        self.assertEqual(self.form.b64zlib, TEST_B64ZLIB)

    def test_b64zlib_decodes_to_original_data(self):
        """Decoding and decompressing b64zlib must recover the original data."""
        recovered = zlib.decompress(b64decode(self.form.b64zlib))
        self.assertEqual(recovered, TEST_DATA)

    def test_placeholder_path(self):
        """path must be set to the ':memory:' placeholder."""
        self.assertEqual(self.form.path, ":memory:")

    def test_no_error(self):
        """error must be None for a successful conversion."""
        self.assertIsNone(self.form.error)


# ---------------------------------------------------------------------------
# write_file_from_form
# ---------------------------------------------------------------------------

class TestWriteFileFromForm(unittest.TestCase):
    """Verify that write_file_from_form writes correct data to disk."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        self.form        = load_form_from_bytes(TEST_DATA)
        self.form.path   = self.path
        self.result_form = write_file_from_form(self.form)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_no_error(self):
        """error must be None after a successful write."""
        self.assertIsNone(self.result_form.error)

    def test_b64zlib_cleared_after_write(self):
        """b64zlib must be cleared (set to None) after a successful write."""
        self.assertEqual(self.result_form.b64zlib, "")

    def test_file_contents_match_test_data(self):
        """The written file must contain exactly TEST_DATA."""
        with open(self.path, 'rb') as fh:
            self.assertEqual(fh.read(), TEST_DATA)

    def test_file_md5sum_matches(self):
        """MD5 of the written file must match TEST_MD5SUM."""
        with open(self.path, 'rb') as fh:
            self.assertEqual(hashlib.md5(fh.read()).hexdigest(), TEST_MD5SUM)

    def test_file_size_matches(self):
        """Size of the written file must match TEST_SIZE."""
        self.assertEqual(os.path.getsize(self.path), TEST_SIZE)


# ---------------------------------------------------------------------------
# load_file_to_form
# ---------------------------------------------------------------------------

class TestLoadFileToForm(unittest.TestCase):
    """Verify that load_file_to_form reads a file and populates the LoadFile form correctly."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.write(fd, TEST_DATA)
        os.close(fd)
        form        = LoadFile(path=self.path)
        self.result = load_file_to_form(form)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_no_error(self):
        """error must be None after a successful load."""
        self.assertIsNone(self.result.error)

    def test_size_is_correct(self):
        """size must equal the uncompressed file size (TEST_SIZE)."""
        self.assertEqual(self.result.size, TEST_SIZE)

    def test_md5sum_is_correct(self):
        """md5sum must equal the hex MD5 digest of the file data (TEST_MD5SUM)."""
        self.assertEqual(self.result.md5sum, TEST_MD5SUM)

    def test_b64zlib_is_correct(self):
        """b64zlib must equal base64(zlib_compress(data, level=9)) (TEST_B64ZLIB)."""
        self.assertEqual(self.result.b64zlib, TEST_B64ZLIB)

    def test_b64zlib_decodes_to_original_data(self):
        """Decoding and decompressing b64zlib must recover the original file data."""
        recovered = zlib.decompress(b64decode(self.result.b64zlib))
        self.assertEqual(recovered, TEST_DATA)


# ---------------------------------------------------------------------------
# load_bytes_from_form
# ---------------------------------------------------------------------------

class TestLoadBytesFromForm(unittest.TestCase):
    """Verify that load_bytes_from_form recovers the original data from a LoadFile form."""

    def _make_form(self) -> LoadFile:
        return LoadFile(
            path=":memory:",
            b64zlib=TEST_B64ZLIB,
            md5sum=TEST_MD5SUM,
            size=TEST_SIZE,
        )

    def test_returns_original_data(self):
        """Return value must equal TEST_DATA."""
        self.assertEqual(load_bytes_from_form(self._make_form()), TEST_DATA)

    def test_raises_on_md5_mismatch(self):
        """Must raise AssertionError when md5sum does not match the decompressed data."""
        form = self._make_form()
        form.md5sum = "0" * 32
        with self.assertRaises(AssertionError):
            load_bytes_from_form(form)

    def test_raises_on_error_field_set(self):
        """Must raise AssertionError when form.error is not None."""
        form = self._make_form()
        form.error = "upstream error"
        with self.assertRaises(AssertionError):
            load_bytes_from_form(form)

    def test_raises_on_corrupt_b64zlib(self):
        """Must raise an exception when b64zlib contains corrupt compressed data."""
        form = self._make_form()
        form.b64zlib = b64encode(b"\x00" * 16).decode()
        with self.assertRaises(Exception):
            load_bytes_from_form(form)


# ---------------------------------------------------------------------------
# Full round-trip: load_form_from_bytes -> write_file -> load_file -> load_bytes
# ---------------------------------------------------------------------------

class TestFileRoundTrip(unittest.TestCase):
    """End-to-end round-trip through all four file utility functions.

    Verifies that data written via load_form_from_bytes + write_file_from_form
    is recovered identically via load_file_to_form + load_bytes_from_form.
    """

    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_round_trip_data_integrity(self):
        """Data must survive a full write-then-read round-trip unchanged."""
        write_form      = load_form_from_bytes(TEST_DATA)
        write_form.path = self.path
        write_file_from_form(write_form)

        load_form = load_file_to_form(LoadFile(path=self.path))
        recovered = load_bytes_from_form(load_form)

        self.assertEqual(recovered, TEST_DATA)

    def test_round_trip_md5sum_consistent(self):
        """md5sum must be consistent across write and read forms."""
        write_form      = load_form_from_bytes(TEST_DATA)
        write_form.path = self.path
        write_file_from_form(write_form)

        load_form = load_file_to_form(LoadFile(path=self.path))

        self.assertEqual(load_form.md5sum, TEST_MD5SUM)

    def test_round_trip_b64zlib_consistent(self):
        """b64zlib produced by load_file_to_form must match the canonical fixture."""
        write_form      = load_form_from_bytes(TEST_DATA)
        write_form.path = self.path
        write_file_from_form(write_form)

        load_form = load_file_to_form(LoadFile(path=self.path))

        self.assertEqual(load_form.b64zlib, TEST_B64ZLIB)

    def test_round_trip_size_consistent(self):
        """size must equal TEST_SIZE after a full round-trip."""
        write_form      = load_form_from_bytes(TEST_DATA)
        write_form.path = self.path
        write_file_from_form(write_form)

        load_form = load_file_to_form(LoadFile(path=self.path))

        self.assertEqual(load_form.size, TEST_SIZE)


if __name__ == '__main__':
    unittest.main()
