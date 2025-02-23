#!/usr/bin/python3
"""This module implements functions and classes for managing datastore files and
linking them to the inventory."""
from typing import Any, Dict

from .collection import Collection
from .object import Object

CHUNK_SIZE = 65536

def new_chunk(datastore: Collection) -> Object:
    """This function creates a new chunk object in the datastore.

    Args:
        datastore:
            collection where the chunk object is stored

    Returns:
        A chunk object with a bytearray in it."""

    chunk = datastore.get_object()
    chunk.object = {
        "data" : bytearray(CHUNK_SIZE),
        "type" : "chunk",
    }
    chunk.set()

    return chunk

def new_sequence(datastore: Collection, sequuid: str = None) -> Object:
    """This function creates a sequence object in the datastore. A
    sequence object acts as a logical group of chunk UUIDs to encapsulate
    a binary file.

    Args:
        sequuid:
            The sequence object's UUID.

        datastore:
            collection where the sequence object is stored

    Returns:
        Returns a sequence object.
    """
    sequence = datastore.get_object(sequuid)
    sequence.object = {
        "chunks" : [],
        "size" : 0,
        "type" : "sequence"
    }
    sequence.set()

    return sequence

def delete_sequence(datastore: Collection, sequuid: str):
    """This function deletes a sequence object and the chunks it points to
    in the datastore.

    Args:
        sequuid:
            The sequence object's UUID.

        datastore:
            collection where the sequence object is stored
    """
    sequence = datastore.get_object(sequuid)

    if "chunks" in sequence.object:
        for chunkid in sequence.object["chunks"]:
            datastore.get_object(chunkid).destroy()

    sequence.destroy()

class File: # pylint: disable=too-many-instance-attributes
    """This class implements a datastore file. The class produces file-like instances that
    facilitate random access IO."""
    def __init__(self, sequuid: str = None, datastore: Collection = Collection("datastore")):
        """This method creates an instance of a datastore file and either loads an existing
        or creates a new datastore sequence for it.

        Args:
            sequuid:
                A sequence UUID.

            datastore:
                collection where the chunk and sequence objects are stored
        """
        self.__position = 0
        self.__chunk_position = 0
        self.__datastore = datastore
        self.__chunk = None
        self.__chunk_index = 0
        self.__chunk_changed = False
        self.__end_of_sequence = False
        self.__following_write = False

        if sequuid in self.__datastore.find_objuuids(type="sequence"):
            self.__sequence = self.__datastore.get_object(sequuid)
            self.__chunk = self.__datastore.get_object(self.__sequence.object["chunks"][0])
        else:
            self.__sequence = new_sequence(self.__datastore, sequuid)
            self.__chunk = new_chunk(self.__datastore)
            self.__sequence.object["chunks"].append(self.__chunk.objuuid)
            self.__sequence.set()

    def __del__(self):
        """This method closes the datastore file."""
        self.close()

    def sequuid(self) -> str:
        """This method returns the datastore file's sequence UUID.

        Returns:
            The datastore file's sequence UUID.
        """
        return self.__sequence.object["objuuid"]

    def delete(self):
        """This method deletes the datastore file's sequence."""
        delete_sequence(self.__datastore, self.__sequence.object["objuuid"])

    def tell(self) -> int:
        """This method returns the datastore file's cursor position.

        Returns:
            The position as an integer.
        """
        return self.__position

    def size(self) -> int:
        """This method returns the size of the datastore file's sequence.

        Returns:
            An integer of the number of bytes.
        """
        return self.__sequence.object["size"]

    def close(self):
        """This method closes the datastore file."""
        self.__sequence.set()
        self.__chunk.set()

    def open(self, **kargs: Dict[str, str]):
        """This method exposes init via open."""
        self.__init__(kargs)

    def seek(self, seek_position: int):
        """This method seeks to a specific position in the file. Seeking resolves
        indexes for the chunk and byte with the chunk's byte array.

        Args:
            seek_position:
                The integer of the position to seek to.
        """
        if seek_position < 0 or seek_position >= self.__sequence.object["size"]:
            raise IndexError("Position out of bounds!")

        i = int(seek_position / CHUNK_SIZE)
        if self.__chunk_index != i:
            if self.__chunk_changed is True:
                self.__chunk.set()

            self.__chunk = self.__datastore.get_object(self.__sequence.object["chunks"][i])
            self.__chunk_index = i

            self.__chunk_changed = False

        self.__chunk_position = seek_position % CHUNK_SIZE

        self.__position = seek_position

        self.__following_write = False

        self.__end_of_sequence = False

    def read(self, num_bytes: int = None) -> bytearray:
        """This method reads bytes from datastore file and returns a bytearray.
        If the number of bytes is unspecified, then the entire file is read.

        Args:
            num_bytes:
                The number of bytes to read starting from the current position.

        Returns:
            A byte array.
        """
        buffer = bytearray()

        if self.__end_of_sequence is True:
            pass
        elif num_bytes is None:
            for _i in range(self.__position, self.__sequence.object["size"]):
                buffer.append(self.__chunk.object["data"][self.__chunk_position])

                try:
                    self.seek(1 + self.__position)
                except IndexError:
                    self.__end_of_sequence = True
                    break
        else:
            for _i in range(self.__position, self.__position + num_bytes):
                buffer.append(self.__chunk.object["data"][self.__chunk_position])

                try:
                    self.seek(1 + self.__position)
                except IndexError:
                    self.__end_of_sequence = True
                    break

        return buffer

    def truncate(self, num_bytes: int = None):
        """This method truncates a datastore file to a given size."""
        if num_bytes is None:
            self.resize(self.__position + 1)
        else:
            self.resize(num_bytes)

    def resize(self, num_bytes: int):
        """This method resizes a datastore file to a given size.

        Args:
            num_bytes:
                The size to make the datastore file in bytes.
        """
        self.__sequence.object["size"] = num_bytes

        num_chunks = int(num_bytes / CHUNK_SIZE) + 1
        num_chunks_exist = len(self.__sequence.object["chunks"])

        if num_chunks_exist < num_chunks:
            for i in range(num_chunks_exist, num_chunks):
                chunk = new_chunk(self.__datastore)
                self.__sequence.object["chunks"].append(chunk.objuuid)
        else:
            for i in range(num_chunks_exist - 1, num_chunks - 1, -1):
                self.__datastore.get_object(self.__sequence.object["chunks"][i]).destroy()
                self.__sequence.object["chunks"].pop()

    def write(self, raw_buffer: Any):
        """This method writes data to the datastore file.

        Args:
            raw_buffer:
               An interable to extend a bytearray with.
        """
        buffer = bytearray()

        buffer.extend(raw_buffer)

        if (
                self.__following_write is True and
                len(buffer) > 0 and
                self.size() < self.__position + len(buffer) + 1
            ):
            self.resize(self.__position + len(buffer) + 1)
            self.seek(1 + self.__position)
        elif (
                self.__following_write is False and
                len(buffer) > 0 and
                self.size() < self.__position + len(buffer)
            ):
            self.resize(self.__position + len(buffer))

        for i in range(0, len(buffer)): # pylint: disable=consider-using-enumerate
            self.__chunk.object["data"][self.__chunk_position] = buffer[i]
            self.__chunk_changed = True

            if i < len(buffer) - 1:
                self.seek(1 + self.__position)

        self.__following_write = True

def copy_file(inp_f: File, out_f: File):
    """This function copies a sequence in the datastore.

    Args:
        inp_f:
            Source file.

        out_f:
            Destination file.
    """

    chunk = inp_f.read(CHUNK_SIZE)
    out_f.write(chunk)

    while len(chunk) > 0:
        chunk = inp_f.read(CHUNK_SIZE)
        out_f.write(chunk)

    out_f.close()
    inp_f.close()
