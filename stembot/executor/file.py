"""File I/O operations with compression and integrity verification.

Provides utilities for reading and writing files as part of control form execution.
All file data is compressed with zlib (compression level 9) and base64-encoded for
transport. Includes MD5 checksum verification to ensure data integrity and SHA-like
hashing for validation.

Supported operations:
- Load files into LoadFile forms with compression and checksums
- Extract bytes from LoadFile forms with integrity verification
- Create WriteFile forms from raw bytes
- Write files from WriteFile forms with decompression and validation

Key features:
- Zlib compression (level 9) for bandwidth efficiency
- Base64 encoding for safe transport
- MD5 checksum verification on read and write
- Exception handling with error logging
"""

from base64 import b64encode, b64decode
import hashlib
import logging
import zlib

from stembot.models.control import LoadFile, WriteFile

def load_file_to_form(form: LoadFile) -> LoadFile:
    """Read a file from disk and populate a LoadFile form with compressed data.

    Opens a file at the specified path, reads its contents, compresses with zlib
    (level 9), encodes as base64, and calculates MD5 checksum. Stores compressed
    data and metadata in the LoadFile form for transmission to remote agents.

    On error, sets form.error with the exception message and returns the form.

    Args:
        form: A LoadFile form with path set to the file to load.

    Returns:
        The same LoadFile form with populated fields:
        - b64zlib: Base64-encoded compressed file contents
        - size: Original uncompressed file size in bytes
        - md5sum: MD5 checksum of original data for integrity verification
        - error: None on success, exception message on failure
    """
    try:
        logging.debug(form.path)
        with open(form.path, 'rb') as file:
            data = file.read()
            form.size = len(data)
            form.md5sum = hashlib.md5(data).hexdigest()
            form.b64zlib = b64encode(zlib.compress(data, level=9)).decode()
            form.error = None
    except Exception as exception: # pylint: disable=broad-except
        form.error = str(exception)
        form.size = None
        form.md5sum = None
        logging.error(form.error)
    return form


def load_bytes_from_form(form: LoadFile) -> bytes:
    """Extract and decompress file data from a LoadFile form.

    Decodes base64 and decompresses zlib data from a LoadFile form, then
    verifies integrity with MD5 checksum comparison. Used to extract the
    original file contents after receiving a LoadFile response from a remote agent.

    Args:
        form: A LoadFile form containing b64zlib (compressed data) and md5sum.

    Returns:
        The original uncompressed file data as bytes.

    Raises:
        AssertionError: If error is set or MD5 checksum verification fails.
        zlib.error: If decompression fails.
    """
    data = zlib.decompress(b64decode(form.b64zlib))
    assert form.error is None
    assert hashlib.md5(data).hexdigest() == form.md5sum
    return data


def load_form_from_bytes(data: bytes) -> WriteFile:
    """Create a WriteFile form from raw bytes.

    Compresses raw data with zlib (level 9), encodes as base64, and calculates
    MD5 checksum. Wraps the compressed data in a WriteFile form ready for
    sending to a remote agent to write to disk.

    Args:
        data: The file contents as raw bytes to write.

    Returns:
        A WriteFile form containing:
        - b64zlib: Base64-encoded compressed data
        - md5sum: MD5 checksum of original data
        - size: Original uncompressed size in bytes
        - path: Set to ':memory:' (placeholder, should be set by caller)
    """
    logging.debug('%s bytes', len(data))
    return WriteFile(
        b64zlib=b64encode(zlib.compress(data, level=9)),
        md5sum=hashlib.md5(data).hexdigest(),
        size=len(data),
        path=':memory:'
    )


def write_file_from_form(form: WriteFile) -> WriteFile:
    """Write file data from a WriteFile form to disk.

    Decompresses zlib-compressed data from a WriteFile form, verifies MD5
    checksum, and writes to the specified path. Verifies the written file
    by re-reading and checking its MD5 matches the original.

    On success, clears b64zlib from the form to save memory. On error, sets
    form.error with the exception message.

    Args:
        form: A WriteFile form with:
            - b64zlib: Base64-encoded compressed file contents
            - path: Destination file path
            - md5sum: Expected MD5 checksum
            - error: Should be None initially

    Returns:
        The same WriteFile form with:
        - error: None on success, exception message on failure
        - b64zlib: Cleared to None on success (to save memory)

    Raises:
        (Caught internally and returned as form.error)
    """
    try:
        logging.debug(form.path)
        with open(form.path, 'wb') as file:
            data = zlib.decompress(b64decode(form.b64zlib))
            assert form.error is None
            assert hashlib.md5(data).hexdigest() == form.md5sum
            file.write(data)
            form.error = None
        with open(form.path, 'rb') as file:
            assert hashlib.md5(file.read()).hexdigest() == form.md5sum
        form.b64zlib = None
    except Exception as exception: # pylint: disable=broad-except
        form.error = str(exception)
        logging.error(form.error)
    return form
