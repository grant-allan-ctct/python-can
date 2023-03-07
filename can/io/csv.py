"""
This module contains handling for CSV (comma separated values) files.

TODO: CAN FD messages are not yet supported.

TODO: This module could use https://docs.python.org/2/library/csv.html#module-csv
      to allow different delimiters for writing, special escape chars to circumvent
      the base64 encoding and use csv.Sniffer to automatically deduce the delimiters
      of a CSV file.
"""

from base64 import b64encode, b64decode
from typing import TextIO, Generator, Union, Any

from can.message import Message
from .generic import FileIOMessageWriter, MessageReader
from ..typechecking import StringPathLike


class CSVReader(MessageReader):
    """Iterator over CAN messages from a .csv file that was
    generated by :class:`~can.CSVWriter` or that uses the same
    format as described there. Assumes that there is a header
    and thus skips the first line.

    Any line separator is accepted.
    """

    file: TextIO

    def __init__(
        self,
        file: Union[StringPathLike, TextIO],
        **kwargs: Any,
    ) -> None:
        """
        :param file: a path-like object or as file-like object to read from
                     If this is a file-like object, is has to opened in text
                     read mode, not binary read mode.
        """
        super().__init__(file, mode="r")

    def __iter__(self) -> Generator[Message, None, None]:
        # skip the header line
        try:
            next(self.file)
        except StopIteration:
            # don't crash on a file with only a header
            return

        for line in self.file:
            timestamp, arbitration_id, extended, remote, error, dlc, data = line.split(
                ","
            )

            yield Message(
                timestamp=float(timestamp),
                is_remote_frame=(remote == "1"),
                is_extended_id=(extended == "1"),
                is_error_frame=(error == "1"),
                arbitration_id=int(arbitration_id, base=16),
                dlc=int(dlc),
                data=b64decode(data),
            )

        self.stop()


class CSVWriter(FileIOMessageWriter):
    """Writes a comma separated text file with a line for
    each message. Includes a header line.

    The columns are as follows:

    ================ ======================= ===============
    name of column   format description      example
    ================ ======================= ===============
    timestamp        decimal float           1483389946.197
    arbitration_id   hex                     0x00dadada
    extended         1 == True, 0 == False   1
    remote           1 == True, 0 == False   0
    error            1 == True, 0 == False   0
    dlc              int                     6
    data             base64 encoded          WzQyLCA5XQ==
    ================ ======================= ===============

    Each line is terminated with a platform specific line separator.
    """

    file: TextIO

    def __init__(
        self,
        file: Union[StringPathLike, TextIO],
        append: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        :param file: a path-like object or a file-like object to write to.
                     If this is a file-like object, is has to open in text
                     write mode, not binary write mode.
        :param bool append: if set to `True` messages are appended to
                            the file and no header line is written, else
                            the file is truncated and starts with a newly
                            written header line
        """
        mode = "a" if append else "w"
        super().__init__(file, mode=mode)

        # Write a header row
        if not append:
            self.file.write("timestamp,arbitration_id,extended,remote,error,dlc,data\n")

    def on_message_received(self, msg: Message) -> None:
        row = ",".join(
            [
                repr(msg.timestamp),  # cannot use str() here because that is rounding
                hex(msg.arbitration_id),
                "1" if msg.is_extended_id else "0",
                "1" if msg.is_remote_frame else "0",
                "1" if msg.is_error_frame else "0",
                str(msg.dlc),
                b64encode(msg.data).decode("utf8"),
            ]
        )
        self.file.write(row)
        self.file.write("\n")
