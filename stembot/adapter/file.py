#!/usr/bin/python3
from base64 import b64encode, b64decode
import hashlib
import traceback
import zlib

from stembot import logging
from stembot.types.control import LoadFile, WriteFile

def load_file_to_form(form: LoadFile) -> LoadFile:
    try:
        logging.debug(form.path)
        with open(form.path, 'rb') as file:
            data = file.read()
            form.size = len(data)
            form.md5sum = hashlib.md5(data).hexdigest()
            form.b64 = b64encode(zlib.compress(data, level=9)).decode()
            form.error = None
    except: # pylint: disable=bare-except
        form.error = traceback.format_exc()
        form.size = None
        form.md5sum = None
        logging.exception(f'Failed to read {form.path}')

    return form


def load_bytes_from_form(form: LoadFile) -> bytes:
    return zlib.decompress(b64decode(form.b64))


def load_form_from_bytes(data: bytes) -> WriteFile:
    logging.debug(f'{len(data)} bytes')
    return WriteFile(
        b64=b64encode(zlib.compress(data, level=9)),
        md5sum=hashlib.md5(data).hexdigest(),
        size=len(data),
        path=':memory:'
    )


def write_file_from_form(form: WriteFile) -> WriteFile:
    try:
        logging.debug(form.path)
        with open(form.path, 'wb') as file:
            file.write(zlib.decompress(b64decode(form.b64)))
            form.error = None
    except: # pylint: disable=bare-except
        form.error = traceback.format_exc()
        logging.exception(f'Failed to write {form.path}')

    return form


